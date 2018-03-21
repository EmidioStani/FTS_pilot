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
    # Read configuration file
    with open(configfile, encoding='utf-8-sig') as json_file:
        config_data = json.load(json_file)
    def_base_uri = config_data['baseuri']
    getValue = config_data['getValue']
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
    os.chdir(os.path.join(cwd,'data/raw'))
    data = read_csv(data_filename, 0)
    session = Session.get_current()

    # Load model from Turtle file
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

    # Create dictionary with all countries
    countriesmodelfile = config_data["countriesmodelfile"]
    def getCountryDict(modelfile):
        countryGraph = rdflib.Graph()
        countryGraph.parse(modelfile)
        countryList = countryGraph.query(
        """SELECT ?uri ?o
           WHERE {
              ?uri skos:prefLabel ?o .
              FILTER (lang(?o) = 'en')
           }
           """)
        countryCode = {}
        for row in countryList:
            countryCode[str(row.o.toPython())] = str(row.uri.toPython())
        return countryCode
    countryList = getCountryDict(countriesmodelfile)

    # Create URI for currency (only EUR for now)
    currencyEUR = config_data["currencyEUR"]

    # Create URI for currency (only EUR for now)
    corporateBodyBase = config_data["corporateBodyBase"]
    corporateBodyReplace = config_data["corporateBodyReplace"]


    #-------------------------------#
    # Create Instances of Dataset   #
    #-------------------------------#
    print('Going over all data to create the objects...')
    with click.progressbar(data.iterrows()) as total:
        for ix, row in total:

            if ix < 2:

                #----------------#
                # Create Address #
                #----------------#
                lbl = "Address" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                Address_tmp = ontology.locnAddress(uri=URISpec)
                Address_tmp.locnadminUnitL1 += countryList.setdefault(row[getValue['countryDescriptionEn']], "Not Found")
                Address_tmp.locnfullAddress += row[getValue['address']]
                Address_tmp.locnpostName += row[getValue['city']]
                Address_tmp.locnpostCode += row[getValue['postCode']]


                #-----------------#
                # Create Location #
                #-----------------#
                lbl = "Location" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                Location_tmp = ontology.dctLocation(uri=URISpec)
                Location_tmp.locngeographicName += row[getValue['recipientName']] + ', ' + row[getValue['city']] + ', ' + row[getValue['countryDescriptionEn']]
                Location_tmp.locnaddress += Address_tmp

                #------------------#
                # Create Recipient #
                #------------------#
                lbl = "Recipient" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                Recipient_tmp = ontology.Recipient(uri=URISpec)
                Recipient_tmp.prefLabel += row[getValue['recipientName']]
                Recipient_tmp.hasLocation += Location_tmp
                recipientType = recipientCatg[row[getValue['recipientTypeDescription']].casefold()]
                recipientURI = Recipient_tmp.getInstanceUri()

                # If needed, an extra type for the Recipient is assigned
                if recipientType == "Registered Organisation":
                    RecipientAlter_tmp = ontology.rovRegisteredOrganization(uri=None, imposeURI=recipientURI)
                    RecipientAlter_tmp.rovlegalName += row[getValue['recipientName']]
                    RecipientAlter_tmp.rovregistration += row[getValue['recipientVAT']]
                    RecipientAlter_tmp.rovorgType += row[getValue['organisationTypeCode']] + ', ' + row[getValue['organisationTypeDescription']]
                elif recipientType == "Public Organisation":
                    RecipientAlter_tmp = ontology.cpovPublicOrganisation(uri=None, imposeURI=recipientURI)
                    # RecipientAlter_tmp.orgclassification += # Should be filled in by value of controlled voc. Where to find? No info in spreadsheet either.
                elif recipientType == "Person":
                    RecipientAlter_tmp = ontology.cpovPublicOrganisation(uri=None, imposeURI=recipientURI)
                    RecipientAlter_tmp.foaffamilyName += row[getValue['recipientName']]
                elif recipientType == "Recipient":
                    pass # Recipient object already made
                elif recipientType == "International Organisation":
                    RecipientAlter_tmp = ontology.InternationalOrganisation(uri=None, imposeURI=recipientURI)
                elif recipientType == "Trust Fund":
                    RecipientAlter_tmp = ontology.TrustFund(uri=None, imposeURI=recipientURI)
                elif recipientType == "NFPO":
                    RecipientAlter_tmp = ontology.NonProfitOrganisation(uri=None, imposeURI=recipientURI)
                    RecipientAlter_tmp.rovregistration += row[getValue['recipientVAT']]
                    RecipientAlter_tmp.rovorgType += row[getValue['organisationTypeCode']] + ', ' + row[getValue['organisationTypeDescription']]
                elif recipientType == "NGO":
                    RecipientAlter_tmp = ontology.NGO(uri=None, imposeURI=recipientURI)
                    RecipientAlter_tmp.rovregistration += row[getValue['recipientVAT']]
                    RecipientAlter_tmp.rovorgType += row[getValue['organisationTypeCode']] + ', ' + row[getValue['organisationTypeDescription']]

                else:
                    print('Recipient: no additional type match.')

                # -------------------------#
                # Create Legal Commitment #
                # -------------------------#
                lbl = "LegalCommitment" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                LegalCommitment_tmp = ontology.LegalCommitment(uri=URISpec)
                LegalCommitment_tmp.dctdescription += row[getValue['subject']]
                LegalCommitment_tmp.fundingType += row[getValue['fundingType']]
                LegalCommitment_tmp.hasCoordinator += Recipient_tmp
                LegalCommitment_tmp.hasActionLocation += Location_tmp # row[getValue['actionLocation']]
                # for action location, should we take the same location as defined in line 77?
                # text in the excel file is different but seems to refer to similar location

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
                IndicativeTransaction_tmp.committedBy += corporateBodyBase + DG
                IndicativeTransaction_tmp.hasEstimatedValue += MonetaryValue_tmp

                # --------------------#
                # Create Position Key #
                # --------------------#
                lbl = "positionKey" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                PositionKey_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['positionKey']])
                # how to incorporate code of positionKey? Used label for now

                # ----------------------#
                # Create Commitment Key #
                # ----------------------#
                lbl = "commitmentKey" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                CommitmentKey_tmp = ontology.admsIdentifier(uri=URISpec, label=row[getValue['commitmentKey']])

                # --------------------#
                # Create Nomenclature # --> link to EU Budget
                # --------------------#

                lbl = "Nomenclature" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                Nomenclature_tmp = ontology.Nomenclature(uri=URISpec)
                Nomenclature_tmp.alias += row[getValue['budgetLine']]
                Nomenclature_tmp.heading += row[getValue['headingEn']]

                # ----------------------------#
                # Create Budgetary Commitment #
                # ----------------------------#
                lbl = "BudgetaryCommitment" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                BudgetaryCommitment_tmp = ontology.BudgetaryCommitment(uri=URISpec)

                BudgetaryCommitment_tmp.positionKey += PositionKey_tmp
                BudgetaryCommitment_tmp.commitmentKey += CommitmentKey_tmp
                BudgetaryCommitment_tmp.dctdate += row[getValue['year']]
                # BudgetaryCommitment_tmp.actionType += row['ACTION_TYPE'] # should be skos: concept
                # BudgetaryCommitment_tmp.financialManagementArea += row['FIN_MGT_AREA_CD'] # should be skos:concept
                # BudgetaryCommitment_tmp.expenseType += row['IS_ADMIN'] # should be skos:concept
                BudgetaryCommitment_tmp.hasBudgetLine += Nomenclature_tmp
                BudgetaryCommitment_tmp.hasTotalValue += MonetaryValue_tmp
                BudgetaryCommitment_tmp.hasIndicativeTransaction += IndicativeTransaction_tmp
                BudgetaryCommitment_tmp.hasLegalCommitment += LegalCommitment_tmp

                # ----------------------#
                # Create Corporate Body # --> link to EU Budget
                # ----------------------#

                # we will link to URI directly.
                # To check how to insert the relevant information


        print('\t\t\t\t\t ... Done.')

    #-----------------------------------------------#
    # Print all triples to file                     #
    #-----------------------------------------------#
    output = open(outputfile,'w')
    for (subject, predicate, obj) in session.rdf_statements():
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
