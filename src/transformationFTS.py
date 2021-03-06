import pandas
import time
from ontology_alchemy import Ontology, Session, URISpecification
import rdflib
import click
import os
import json
import inspect

# load config file and default input options
configfile = 'config.json'
with open(configfile, encoding='utf-8-sig') as json_file:
    config_data = json.load(json_file)
defaultinputfile = config_data['defaultinputfile']
defaultmodelfile = config_data['defaultmodelfile']
defaultoutputfile = config_data['defaultoutputfile']
defaultcompressionlevel = config_data['defaultcompressionlevel']

@click.command()
@click.option('--inputfile', default=defaultinputfile, help='Input data in csv.')
@click.option('--model', default=defaultmodelfile, help='The ttl model to use.')
@click.option('--configfile', default=configfile, help='The configuration file to use.')
@click.option('--outputfile', default=defaultoutputfile, help='The output file to write to.')
@click.option('--compression', default=defaultcompressionlevel, help='The compression level (0, 1 or 2).')

def main(inputfile,model,configfile,outputfile,compression):

    compression = int(compression)

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

    # Load Public Organisation dictionary
    publicOrganisationCatg = config_data['publicOrganisationCatg']
    publicOrganisationCatg_new = dict()
    for key in publicOrganisationCatg:
        newkey = key.casefold()
        publicOrganisationCatg_new[newkey] = publicOrganisationCatg[key]
    publicOrganisationCatg = publicOrganisationCatg_new

    nomenclatureBase = config_data['nomenclatureBase']

    #------------------------#
    # Load model and data    #
    #------------------------#

    # Set filenames
    data_filename = inputfile
    model_filename = model

    cwd = os.getcwd()
    # Load data
    print('Loading data...')
    os.chdir(os.path.join(cwd,'data/raw'))
    data = pandas.read_csv(data_filename, sep=',', encoding = "ANSI", quotechar='"', na_filter=False, low_memory=False)
    data = data.replace({'\n': ', '}, regex=True) # remove newline characters in data
    session = Session.get_current()
    # Load model from Turtle file
    print('Loading model...')
    os.chdir(os.path.join(cwd,'models'))
    ontology = Ontology.load(model_filename)
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

    # Query a file to get a dictionary with keys 'o' and values 'uri'
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

    # Create dictionary of Countries
    countriesmodelfile = config_data["countriesmodelfile"]
    countryList = getQueryDict(countriesmodelfile)
    countryNotFoundBase = config_data["countryNotFoundBase"]
    countryReplace = config_data["countryReplace"]

    # Create URI for currency (only EUR for now)
    currencyEUR = config_data["currencyEUR"]

    # Create URI for corporate Body
    corporateBodyBase = config_data["corporateBodyBase"]
    corporateBodyReplace = config_data["corporateBodyReplace"]

    # set up dictionaries for controlled vocabularies
    organisationTypeDict = {}
    corporatebodyDict = {}
    actionTypeDict = {}

    def checkControlledDictionary(controlledDict,keyLabel,valueLabel,label,base_uri=def_base_uri):
        # updates the controlled vocabulary and return the skos Concept URI to be used
        if row[getValue[keyLabel]] not in controlledDict:
            if base_uri == def_base_uri:
                lbl = label + row[getValue[valueLabel]]
                URISpec = URISpecification(base_uri,lbl)
                Concept_tmp = ontology.skosConcept(uri=URISpec)
            else:
                Concept_tmp = ontology.skosConcept(uri=None, imposeURI=base_uri + row[getValue[keyLabel]])
            Concept_tmp.skosprefLabel += row[getValue[valueLabel]]
            controlledDict[row[getValue[keyLabel]]] = Concept_tmp.getInstanceUri()
        return controlledDict[row[getValue[keyLabel]]]

    #-------------------------------#
    # Create Instances of Dataset   #
    #-------------------------------#

    flushfrequency = int(config_data['flushfrequency']) #nb of rows before flushing the data to file.
    batchlimits = range(flushfrequency,len(data.index),flushfrequency)
    output = open(outputfile,'w',encoding='utf8')

    # Go through the data file creating all instances
    with click.progressbar(data.iterrows(), label='Creating instances', length=len(data.index)) as total:
        for ix, row in total:

            if ix < numberOfRowsToConsider or numberOfRowsToConsider == -1:

                #----------------#
                # Create Address #
                #----------------#
                country = row[getValue['countryDescriptionEn']]
                if country in countryReplace:
                    country = countryReplace[country]
                lbl = row[getValue['address']] + row[getValue['city']] + row[getValue['postCode']] + country
                URISpec = URISpecification(def_base_uri,lbl)
                Address_tmp = ontology.locnAddress(uri=URISpec)
                Address_tmp.locnadminUnitL1 += countryList.setdefault(country, countryNotFoundBase + country)
                Address_tmp.locnfullAddress += row[getValue['address']]
                Address_tmp.locnpostName += row[getValue['city']]
                Address_tmp.locnpostCode += row[getValue['postCode']]


                #-----------------#
                # Create Location #
                #-----------------#
                geographicName = str(row[getValue['recipientName']]) + ', ' + str(row[getValue['city']]) + ', ' + str(row[getValue['countryDescriptionEn']])
                URISpec = URISpecification(def_base_uri,geographicName)
                Location_tmp = ontology.dctLocation(uri=URISpec)
                Location_tmp.locngeographicName += geographicName
                Location_tmp.locnaddress += Address_tmp

                #------------------#
                # Create Recipient #
                #------------------#
                lbl = row[getValue['recipientName']] + geographicName
                URISpec = URISpecification(def_base_uri,lbl)
                Recipient_tmp = ontology.Recipient(uri=URISpec)
                Recipient_tmp.prefLabel += row[getValue['recipientName']]
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
                    lbl = row[getValue['recipientVAT']]
                    URISpec = URISpecification(def_base_uri,lbl)
                    RecipientVAT_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['recipientVAT']])
                    RecipientAlter_tmp.rovregistration += RecipientVAT_tmp
                    RecipientAlter_tmp.rovorgType += checkControlledDictionary(organisationTypeDict,'organisationTypeCode','organisationTypeDescription','RegisteredOrganisation')
                elif recipientType == "Public Organisation":
                    RecipientAlter_tmp = ontology.cpovPublicOrganisation(uri=None, imposeURI=recipientURI)
                    RecipientAlter_tmp.orgclassification += publicOrganisationCatg[row[getValue['recipientTypeDescription']].casefold()] # literal for the pilot
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
                    lbl = row[getValue['recipientVAT']]
                    URISpec = URISpecification(def_base_uri,lbl)
                    RecipientVAT_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['recipientVAT']])
                    RecipientAlter_tmp.rovregistration += RecipientVAT_tmp
                    RecipientAlter_tmp.rovorgType += checkControlledDictionary(organisationTypeDict,'organisationTypeCode','organisationTypeDescription','NFPO')
                elif recipientType == "NGO":
                    RecipientAlter_tmp = ontology.NGO(uri=None, imposeURI=recipientURI)
                    lbl = row[getValue['recipientVAT']]
                    URISpec = URISpecification(def_base_uri,lbl)
                    RecipientVAT_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['recipientVAT']])
                    RecipientAlter_tmp.rovregistration += RecipientVAT_tmp
                    RecipientAlter_tmp.rovorgType += checkControlledDictionary(organisationTypeDict,'organisationTypeCode','organisationTypeDescription','NGO')
                else:
                    print('Recipient: no additional type match.')

                # -----------------------#
                # Create Action Location #
                # -----------------------#
                actionlbl = row[getValue['actionLocation']]
                if actionlbl:
                    URISpec = URISpecification(def_base_uri,actionlbl)
                    ActionLocation_tmp = ontology.dctLocation(uri=URISpec)
                    ActionLocation_tmp.locngeographicName += row[getValue['actionLocation']]

                # --------------------#
                # Create Contract Key #
                # --------------------#
                lbl = str(row[getValue['contractKey']])
                URISpec = URISpecification(def_base_uri,lbl)
                ContractKey_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['contractKey']])


                # ------------------------#
                # Create Legal Commitment #
                # ------------------------#
                lbl = str(row[getValue['commitmentKey']])
                URISpec = URISpecification(def_base_uri,lbl)
                LegalCommitment_tmp = ontology.LegalCommitment(uri=URISpec)
                LegalCommitment_tmp.dctdescription += row[getValue['subject']]
                LegalCommitment_tmp.fundingType += row[getValue['fundingType']]
                LegalCommitment_tmp.contractKey += ContractKey_tmp
                if row[getValue['isCoordinator']]:
                    LegalCommitment_tmp.hasCoordinator += Recipient_tmp
                if actionlbl:
                    LegalCommitment_tmp.hasActionLocation += ActionLocation_tmp


                # ----------------------#
                # Create Monetary Value # --> link to EU Budget
                # ----------------------#
                lbl = str(row[getValue['totalValue']])
                URISpec = URISpecification(def_base_uri,lbl)
                MonetaryValue_tmp = ontology.MonetaryValue(uri=URISpec)
                MonetaryValue_tmp.value += row[getValue['totalValue']]
                MonetaryValue_tmp.currency += currencyEUR

                # ------------------------------#
                # Create Indicative Transaction #
                # ------------------------------#
                lbl = row[getValue['DG']] + row[getValue['recipientName']] + str(row[getValue['totalValue']]) + geographicName
                URISpec = URISpecification(def_base_uri,lbl)
                IndicativeTransaction_tmp = ontology.IndicativeTransaction(uri=URISpec)
                IndicativeTransaction_tmp.committedTo += Recipient_tmp
                # construct corporate body uri
                DG = row[getValue['DG']]
                if DG in corporateBodyReplace:
                    DG = corporateBodyReplace[DG]
                IndicativeTransaction_tmp.committedBy += checkControlledDictionary(corporatebodyDict,'DG','DGDescriptionEn','CorporateBody',base_uri=corporateBodyBase)
                IndicativeTransaction_tmp.hasEstimatedValue += MonetaryValue_tmp

                # --------------------#
                # Create Position Key #
                # --------------------#
                lbl = str(row[getValue['positionKey']])
                URISpec = URISpecification(def_base_uri,lbl)
                PositionKey_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['positionKey']])

                # ----------------------#
                # Create Commitment Key #
                # ----------------------#
                lbl = str(row[getValue['commitmentKey']])
                URISpec = URISpecification(def_base_uri,lbl)
                CommitmentKey_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['commitmentKey']])

                # --------------------#
                # Create Nomenclature # --> link to EU Budget
                # --------------------#
                nomenclatureURI = nomenclatureBase + str(row[getValue['year']]) + '_SEC3' + row[getValue['budgetLine']].replace('.','_')

                # ----------------------------#
                # Create Budgetary Commitment #
                # ----------------------------#
                lbl = str(row[getValue['positionKey']]) + row[getValue['financialManagementArea']] + str(row[getValue['expenseType']]) + str(row[getValue['commitmentKey']]) + str(row[getValue['totalValue']])
                URISpec = URISpecification(def_base_uri,lbl)
                BudgetaryCommitment_tmp = ontology.BudgetaryCommitment(uri=URISpec)
                BudgetaryCommitment_tmp.positionKey += PositionKey_tmp
                BudgetaryCommitment_tmp.commitmentKey += CommitmentKey_tmp
                BudgetaryCommitment_tmp.dctdate += row[getValue['year']]
                actionTypeVal = checkControlledDictionary(actionTypeDict,'actionType','actionTypeDescriptionEn','actionType')
                BudgetaryCommitment_tmp.actionType += actionTypeVal
                financialManagementAreaBase = config_data['financialManagementAreaBase']
                BudgetaryCommitment_tmp.financialManagementArea += financialManagementAreaBase + row[getValue['financialManagementArea']]
                expenseTypeBase = config_data['expenseTypeBase']
                expenseTypeMap = config_data['expenseTypeMap']
                BudgetaryCommitment_tmp.expenseType += expenseTypeBase + expenseTypeMap[str(row[getValue['expenseType']])]
                BudgetaryCommitment_tmp.hasBudgetLine += nomenclatureURI
                BudgetaryCommitment_tmp.hasTotalValue += MonetaryValue_tmp
                BudgetaryCommitment_tmp.hasLegalCommitment += LegalCommitment_tmp
                BudgetaryCommitment_tmp.hasIndicativeTransaction += IndicativeTransaction_tmp


                # ----------------------#
                # Create Corporate Body # --> link to EU Budget
                # ----------------------#

                # we will link to URI directly in indicative transaction

                #-----------------------------------------------#
                # Print triples so far to file                  #
                #-----------------------------------------------#

                if ix in batchlimits:
                    flushToFile(session,output,compression)

    flushToFile(session,output,compression)
    output.close()

    # ----------------------------#
    # Transform triples to Turtle #
    # ----------------------------#

    if compression > 1:
        print('Transforming the generated triples to Turtle...')
        g = rdflib.Graph()
        g.parse(outputfile, format="nt")
        ttloutput = outputfile.rsplit('.')
        g.serialize(destination=ttloutput[0] + '.ttl',format='turtle')


def flushToFile(session,output,compression):
    # briefly compute total numer of lines to get a time estimate
    nbrdfstatements = 0
    if compression > 0:
        tripleset = set(session.rdf_statements())
    else:
        tripleset = session.rdf_statements()

    for (subject, predicate, obj) in tripleset:
        nbrdfstatements += 1

    # generate all triples and write to file
    with click.progressbar(tripleset, label='Saving to file    ', length=nbrdfstatements) as total:
        for (subject, predicate, obj) in total:
            if 'ontology_alchemy.base' in str(type(obj)):
                output.write("<%s> <%s> <%s> .\n" % (subject, predicate, obj.uri))
            else:
                if isinstance(obj, str) and obj.startswith("http://"):
                    obj = obj.replace(' ',"_")
                    output.write("<%s> <%s> <%s> .\n" % (subject, predicate, obj))
                else:
                    if isinstance(obj, str) and ('\\' in obj or '"' in obj):
                        obj = obj.replace('"',"''") # replace double quotes by two single quotes
                        obj = obj.replace('\\','\\\\').replace(r'\\\\',r'\\') # escape backslashes
                    output.write('<%s> <%s> "%s" .\n' % (subject, predicate, obj))

    # clear Session
    session.clear()
    session = Session.get_current()

if __name__ == "__main__":
    main()
