import pandas
import time
from ontology_alchemy import Ontology, Session, URISpecification
import rdflib
import click
import os
import json

# load config file
with open('config.json', encoding='utf-8-sig') as json_file:
    config_data = json.load(json_file)
defaultinputfile = config_data['defaultinputfile']
defaultmodelfile = config_data['defaultmodelfile']
defaultoutputfile = config_data['defaultoutputfile']

@click.command()
@click.option('--inputfile', default=defaultinputfile, help='Input data in csv.')
@click.option('--model', default=defaultmodelfile, help='The ttl model to use.')
@click.option('--configfile', default='config.json', help='The configuration file to use.')
@click.option('--outputfile', default=defaultoutputfile, help='The output file to write to.')

def main(inputfile,model,configfile,outputfile):

    print('Loading configuration file...')
    # Read configuration file
    with open(configfile, encoding='utf-8-sig') as json_file:
        config_data = json.load(json_file)
    def_base_uri = config_data['baseuri']
    getValue = config_data['getValue']
    numberOfRowsToConsider = int(config_data['numberOfRowsToConsider'])
    # Load Recipient Categorisation dictionary
    recipientCatg = config_data['recipientCatg']
    recipientCatg_new = dict()
    for key in recipientCatg:
        newkey = key.casefold()
        recipientCatg_new[newkey] = recipientCatg[key]
    recipientCatg = recipientCatg_new

    # Set filenames
    data_filename = inputfile
    model_filename = model

    cwd = os.getcwd()
    # Load data
    print('Loading data...')
    os.chdir(os.path.join(cwd,'data/raw'))
    data = read_csv(data_filename, 0)
    session = Session.get_current()

    # Load model from Turtle file
    print('Loading model...')
    os.chdir(os.path.join(cwd,'models'))
    ontology = load_ontology(model_filename)
    os.chdir(cwd)

    #-------------------------------#
    # Print all classes detected    #
    #-------------------------------#

    if False:
        print("List of all terms detected:")
        for term in ontology.__terms__:
            print(term)
        print('')

    #----------------------------------#
    # Load all controlled vocabularies #
    #----------------------------------#

    print('Loading controlled vocabularies...')
    # Create dictionary with all countries
    countriesmodelfile = config_data["countriesmodelfile"]
    def getQueryDict(modelfile):
        graph = rdflib.Graph()
        graph.parse(modelfile)
        rowlist = graph.query(
        """PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?uri ?o
               WHERE {
                  ?uri skos:prefLabel ?o .
                  FILTER (lang(?o) = 'en')
               }""")
        objdict = {}
        for row in rowlist:
            objdict[str(row.o.toPython())] = str(row.uri.toPython())
        return objdict

    start = time.time()
    countryList = getQueryDict(countriesmodelfile)
    end = time.time()
    print('   ... elapsed time: ',end - start)


    # Create URI for currency (only EUR for now)
    currencyEUR = config_data["currencyEUR"]

    # Create URI for corporate Body
    corporateBodyBase = config_data["corporateBodyBase"]
    corporateBodyReplace = config_data["corporateBodyReplace"]

    # set up dictionaries for controlled vocabularies
    organisationTypeDict = {}
    corporatebodyDict = {}
    # EUProgrammeDict = {}
    actionTypeDict = {}

    def checkControlledDictionary(controlledDict,keyLabel,valueLabel,label):
        # updates the controlled vocabulary and return the skos Concept URI to be used
        if row[getValue[keyLabel]] not in controlledDict:
            lbl = label + str(ix)
            URISpec = URISpecification(def_base_uri,{"label":lbl})
            Concept_tmp = ontology.skosConcept(uri=URISpec)
            Concept_tmp.skosprefLabel += row[getValue[valueLabel]]
            controlledDict[row[getValue[keyLabel]]] = Concept_tmp.getInstanceUri()
        return controlledDict[row[getValue[keyLabel]]]

    #-------------------------------#
    # Create Instances of Dataset   #
    #-------------------------------#

    # Create dictionaries
    addressDict = {} # fulladdress as key
    locationDict = {} # geographicName as key
    recipientDict = {} # prefLabel as key
    actionLocationDict = {}
    legalCommitmentDict = {}
    indicativeTransactionDict = {} # not sure if it makes sense? No obvious key
    budgetaryCommitmentDict = {}
    positionKeyDict = {}
    commitmentKeyDict = {}
    nomenclatureDict = {}

    # Go through the data file creating all instances
    with click.progressbar(data.iterrows(), label='Creating instances', length=len(data.index)) as total:
        for ix, row in total:

            if ix < numberOfRowsToConsider:
                #----------------#
                # Create Address #
                #----------------#
                if row[getValue['address']] in addressDict:
                    Address_tmp = addressDict[row[getValue['address']]]
                else:
                    lbl = "Address" + str(ix)
                    URISpec = URISpecification(def_base_uri,{"label":lbl})
                    Address_tmp = ontology.locnAddress(uri=URISpec)
                    Address_tmp.locnadminUnitL1 += countryList.setdefault(row[getValue['countryDescriptionEn']], "Not Found")
                    Address_tmp.locnfullAddress += row[getValue['address']]
                    Address_tmp.locnpostName += row[getValue['city']]
                    if str(row[getValue['postCode']]) != "nan":
                        Address_tmp.locnpostCode += row[getValue['postCode']]
                    addressDict[row[getValue['address']]] = Address_tmp


                #-----------------#
                # Create Location #
                #-----------------#
                geographicName = str(row[getValue['recipientName']]) + ', ' + str(row[getValue['city']]) + ', ' + str(row[getValue['countryDescriptionEn']])
                if str(geographicName) != "nan":
                    if geographicName in locationDict:
                        Location_tmp = locationDict[geographicName]
                    else:
                        lbl = "Location" + str(ix)
                        URISpec = URISpecification(def_base_uri,{"label":lbl})
                        Location_tmp = ontology.dctLocation(uri=URISpec)
                        Location_tmp.locngeographicName += geographicName
                        Location_tmp.locnaddress += Address_tmp
                        addressDict[geographicName] = Location_tmp


                #------------------#
                # Create Recipient #
                #------------------#
                if row[getValue['recipientName']] in recipientDict:
                    Recipient_tmp = recipientDict[row[getValue['recipientName']]]
                else:
                    lbl = "Recipient" + str(ix)
                    URISpec = URISpecification(def_base_uri,{"label":lbl})
                    Recipient_tmp = ontology.Recipient(uri=URISpec)
                    Recipient_tmp.prefLabel += row[getValue['recipientName']]
                    if str(geographicName) != "nan":
                        Recipient_tmp.hasLocation += Location_tmp
                    recipientType = recipientCatg[row[getValue['recipientTypeDescription']].casefold()]
                    recipientURI = Recipient_tmp.getInstanceUri()

                    # Enforce extra indicator fields
                    if row[getValue['isNaturalPerson']]:
                        recipientType = "Person"
                    elif row[getValue['isNFPO']]:
                        recipientType = "NFPO"
                    elif row[getValue['isNGO']]:
                        recipientType = "NGO"

                    # If needed, an extra type for the Recipient is assigned
                    if recipientType == "Registered Organisation":
                        RecipientAlter_tmp = ontology.rovRegisteredOrganization(uri=None, imposeURI=recipientURI)
                        RecipientAlter_tmp.rovlegalName += row[getValue['recipientName']]
                        if str(row[getValue['recipientVAT']]) != "nan":
                            RecipientAlter_tmp.rovregistration += row[getValue['recipientVAT']]
                        RecipientAlter_tmp.rovorgType += checkControlledDictionary(organisationTypeDict,'organisationTypeCode','organisationTypeDescription','RegisteredOrganisation')
                    elif recipientType == "Public Organisation":
                        RecipientAlter_tmp = ontology.cpovPublicOrganisation(uri=None, imposeURI=recipientURI)
                        # RecipientAlter_tmp.orgclassification += # Should be filled in by value of controlled voc. Where to find? No info in spreadsheet either.
                    elif recipientType == "Person":
                        RecipientAlter_tmp = ontology.foafPerson(uri=None, imposeURI=recipientURI)
                        RecipientAlter_tmp.foaffamilyName += row[getValue['recipientName']]
                    elif recipientType == "Recipient":
                        pass # Recipient object already made
                    elif recipientType == "International Organisation":
                        RecipientAlter_tmp = ontology.InternationalOrganization(uri=None, imposeURI=recipientURI)
                    elif recipientType == "Trust Fund":
                        RecipientAlter_tmp = ontology.TrustFund(uri=None, imposeURI=recipientURI)
                    elif recipientType == "NFPO":
                        RecipientAlter_tmp = ontology.NonProfitOrganisation(uri=None, imposeURI=recipientURI)
                        if str(row[getValue['recipientVAT']]) != "nan":
                            RecipientAlter_tmp.rovregistration += row[getValue['recipientVAT']]
                        RecipientAlter_tmp.rovorgType += checkControlledDictionary(organisationTypeDict,'organisationTypeCode','organisationTypeDescription','NFPO')
                    elif recipientType == "NGO":
                        RecipientAlter_tmp = ontology.NGO(uri=None, imposeURI=recipientURI)
                        if str(row[getValue['recipientVAT']]) != "nan":
                            RecipientAlter_tmp.rovregistration += row[getValue['recipientVAT']]
                        RecipientAlter_tmp.rovorgType += checkControlledDictionary(organisationTypeDict,'organisationTypeCode','organisationTypeDescription','NGO')
                    else:
                        print('Recipient: no additional type match.')

                    recipientDict[row[getValue['recipientName']]] = Recipient_tmp

                # -----------------------#
                # Create Action Location #
                # -----------------------#
                if str(row[getValue['actionLocation']]) != "nan":
                    if row[getValue['actionLocation']] in actionLocationDict:
                        ActionLocation_tmp = actionLocationDict[row[getValue['actionLocation']]]
                    else:
                        lbl = "ActionLocation" + str(ix)
                        URISpec = URISpecification(def_base_uri,{"label":lbl})
                        ActionLocation_tmp = ontology.dctLocation(uri=URISpec)
                        ActionLocation_tmp.locngeographicName += row[getValue['actionLocation']]
                        actionLocationDict[row[getValue['actionLocation']]] = ActionLocation_tmp


                # ------------------------#
                # Create Legal Commitment #
                # ------------------------#
                if row[getValue['subject']] in legalCommitmentDict:
                    LegalCommitment_tmp = legalCommitmentDict[row[getValue['subject']]]
                else:
                    lbl = "LegalCommitment" + str(ix)
                    URISpec = URISpecification(def_base_uri,{"label":lbl})
                    LegalCommitment_tmp = ontology.LegalCommitment(uri=URISpec)
                    LegalCommitment_tmp.dctdescription += row[getValue['subject']]
                    LegalCommitment_tmp.fundingType += row[getValue['fundingType']]
                if row[getValue['isCoordinator']]:
                    LegalCommitment_tmp.hasCoordinator += Recipient_tmp
                if str(row[getValue['actionLocation']]) != "nan":
                    LegalCommitment_tmp.hasActionLocation += ActionLocation_tmp
                legalCommitmentDict[row[getValue['subject']]] = LegalCommitment_tmp

                # ----------------------#
                # Create Monetary Value # --> link to EU Budget
                # ----------------------#
                lbl = "MonetaryValue" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                MonetaryValue_tmp = ontology.MonetaryValue(uri=URISpec)
                MonetaryValue_tmp.value += row[getValue['totalValue']]
                MonetaryValue_tmp.currency += currencyEUR

                # ------------------------------#
                # Create Indicative Transaction #
                # ------------------------------#
                lbl = "IndicativeTransaction" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                IndicativeTransaction_tmp = ontology.IndicativeTransaction(uri=URISpec)
                IndicativeTransaction_tmp.committedTo += Recipient_tmp
                # construct corporate body uri
                DG = row[getValue['DG']]
                if DG in corporateBodyReplace:
                    DG = corporateBodyReplace[DG]
                IndicativeTransaction_tmp.committedBy += checkControlledDictionary(corporatebodyDict,'DG','DGDescriptionEn','CorporateBody')
                IndicativeTransaction_tmp.hasEstimatedValue += MonetaryValue_tmp

                # --------------------#
                # Create Position Key #
                # --------------------#
                if row[getValue['positionKey']] in positionKeyDict:
                    PositionKey_tmp = positionKeyDict[row[getValue['positionKey']]]
                else:
                    lbl = "positionKey" + str(ix)
                    URISpec = URISpecification(def_base_uri,{"label":lbl})
                    PositionKey_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['positionKey']])
                    positionKeyDict[row[getValue['positionKey']]] = PositionKey_tmp

                # ----------------------#
                # Create Commitment Key #
                # ----------------------#
                if row[getValue['commitmentKey']] in commitmentKeyDict:
                    CommitmentKey_tmp = commitmentKeyDict[row[getValue['commitmentKey']]]
                else:
                    lbl = "commitmentKey" + str(ix)
                    URISpec = URISpecification(def_base_uri,{"label":lbl})
                    CommitmentKey_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['commitmentKey']])
                    commitmentKeyDict[row[getValue['commitmentKey']]] = CommitmentKey_tmp

                # --------------------#
                # Create Nomenclature # --> link to EU Budget
                # --------------------#
                if row[getValue['budgetLine']] in nomenclatureDict:
                    Nomenclature_tmp = nomenclatureDict[row[getValue['budgetLine']]]
                else:
                    lbl = "Nomenclature" + str(ix)
                    URISpec = URISpecification(def_base_uri,{"label":lbl})
                    Nomenclature_tmp = ontology.Nomenclature(uri=URISpec)
                    Nomenclature_tmp.alias += row[getValue['budgetLine']]
                    Nomenclature_tmp.heading += row[getValue['headingEn']]
                    nomenclatureDict[row[getValue['budgetLine']]] = Nomenclature_tmp

                # ----------------------------#
                # Create Budgetary Commitment #
                # ----------------------------#
                if row[getValue['positionKey']] in budgetaryCommitmentDict:
                    BudgetaryCommitment_tmp = budgetaryCommitmentDict[row[getValue['positionKey']]]
                else:
                    lbl = "BudgetaryCommitment" + str(ix)
                    URISpec = URISpecification(def_base_uri,{"label":lbl})
                    BudgetaryCommitment_tmp = ontology.BudgetaryCommitment(uri=URISpec)
                    BudgetaryCommitment_tmp.positionKey += PositionKey_tmp
                    BudgetaryCommitment_tmp.commitmentKey += CommitmentKey_tmp
                    BudgetaryCommitment_tmp.dctdate += row[getValue['year']]
                    actionTypeVal = checkControlledDictionary(actionTypeDict,'actionType','actionTypeDescriptionEn','actionType')
                    if str(actionTypeVal) != "nan":
                        BudgetaryCommitment_tmp.actionType += actionTypeVal
                    financialManagementAreaBase = config_data['financialManagementAreaBase']
                    BudgetaryCommitment_tmp.financialManagementArea += financialManagementAreaBase + row[getValue['financialManagementArea']]
                    expenseTypeBase = config_data['expenseTypeBase']
                    expenseTypeMap = config_data['expenseTypeMap']
                    BudgetaryCommitment_tmp.expenseType += expenseTypeBase + expenseTypeMap[str(row[getValue['expenseType']])] # should be skos:concept
                    BudgetaryCommitment_tmp.hasBudgetLine += Nomenclature_tmp
                    BudgetaryCommitment_tmp.hasTotalValue += MonetaryValue_tmp
                    BudgetaryCommitment_tmp.hasLegalCommitment += LegalCommitment_tmp
                BudgetaryCommitment_tmp.hasIndicativeTransaction += IndicativeTransaction_tmp
                budgetaryCommitmentDict[row[getValue['positionKey']]] = BudgetaryCommitment_tmp

                # ----------------------#
                # Create Corporate Body # --> link to EU Budget
                # ----------------------#

                # we will link to URI directly in indicative transaction

    #-----------------------------------------------#
    # Print all triples to file                     #
    #-----------------------------------------------#
    # briefly compute total numer of lines to get a time estimatedValue
    nbrdfstatements = 0
    for (subject, predicate, obj) in session.rdf_statements():
        nbrdfstatements += 1

    output = open(outputfile,'w')
    with click.progressbar(session.rdf_statements(), label='Printing triples', length=nbrdfstatements) as total:
        for (subject, predicate, obj) in total:
            if obj not in session.instances:
                if isinstance(obj, str) and obj.startswith("http://"):
                    output.write("<%s> <%s> <%s> .\n" % (subject, predicate, obj))
                else:
                    output.write('<%s> <%s> "%s" .\n' % (subject, predicate, obj))
            else:
                output.write("<%s> <%s> <%s> .\n" % (subject, predicate, obj.uri))



def read_csv(filename, columns):
    df = pandas.read_csv(filename, sep=',', encoding = "ANSI", quotechar='"')#, names=columns)
    # data = df.values
    # print(df['AMNT'])
    # print(data[19,:]) # some tricky lines to do a sanity check
    # print(data[23433,:])
    return df

def load_ontology(filename):
    ontology = Ontology.load(filename)
    return ontology

def transform_to_csv(filename):
    filename_csv = 'FTS.csv'
    in2csv(filename, filename_csv)
    return filename_csv

def findClass(classname):
    uri = "error no label found"
    for klass in Session.get_current().classes:
        class_string = str(klass).split('.')
        class_string = class_string[-1].split("'")
        if str(class_string[0]) == classname:
            uri = klass.__uri__
    return uri



if __name__ == "__main__":
    main()
