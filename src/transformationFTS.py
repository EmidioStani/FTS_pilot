import pandas
import time
from ontology_alchemy import Ontology, Session, URISpecification
import click
import os
from time import sleep
import re
import json

@click.command()
@click.option('--inputdata', default='FTS.csv', help='Input data in csv.')
@click.option('--model', default='FTS.ttl', help='The ttl model to use.')

def main(inputdata,model):
    # Read configuration file
    with open('config.json', encoding='utf-8-sig') as json_file:
        config_data = json.load(json_file)
    def_base_uri = config_data['baseuri']
    outputfile = config_data['outputfile']
    columns = config_data['columns']
    # Load Recipient Categorisation dictionary
    recipientCatg = config_data['recipientCatg']
    recipientCatg_new = dict()
    for key in recipientCatg:
        newkey = key.casefold()
        recipientCatg_new[newkey] = recipientCatg[key]
    recipientCatg = recipientCatg_new

    # Set filenames
    data_filename = inputdata
    model_filename = model

    cwd = os.getcwd()
    # Load data
    os.chdir(os.path.join(cwd,'data/raw'))
    data = read_csv(data_filename, columns)
    session = Session.get_current()

    # Load model from Turtle file
    os.chdir(os.path.join(cwd,'models'))
    ontology = load_ontology(model_filename)
    os.chdir(cwd)

    #-------------------------------#
    # Print all classes detected    #
    #-------------------------------#

    if True:
        print("List of all terms detected:")
        for term in ontology.__terms__:
            print(term)
        print('')

    #-------------------------------#
    # Create Instances of Dataset   #
    #-------------------------------#
    print('Going over all data to create the objects...')
    with click.progressbar(data.iterrows()) as total:
        for ix, row in total:

            if ix < 2:
                #-----------------#
                # Create Location #
                #-----------------#
                lbl = "Location" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                Location_tmp = ontology.dctLocation(uri=URISpec)
                Location_tmp.locngeographicName += row['LE_NAME'] + ', ' + row['CITY'] + ', ' + row['COUNTRY_DESC_EN']
                # Address needed?

                #------------------#
                # Create Recipient #
                #------------------#
                lbl = "Recipient" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                Recipient_tmp = ontology.Recipient(uri=URISpec)
                Recipient_tmp.prefLabel += row['LE_NAME']
                Recipient_tmp.hasLocation += Location_tmp
                # If needed, an extra type for the Recipient is assigned
                if recipientCatg[row['LE_ACCOUNT_GROUP_DESC'].casefold()] == "Recipient":
                    pass # Recipient object already made
                elif recipientCatg[row['LE_ACCOUNT_GROUP_DESC'].casefold()] == "Public Organisation":
                    RecipientAlter_tmp = ontology.cpovPublicOrganisation(uri=None, imposeURI=Recipient_tmp.getInstanceUri())
                    # RecipientAlter_tmp.prefLabel += row['LE_NAME'] # not needed since already set for Recipient
                    # RecipientAlter_tmp.orgclassification += # Should be filled in by value of controlled voc. Can be found online
                elif recipientCatg[row['LE_ACCOUNT_GROUP_DESC'].casefold()] == "Registered Organisation":
                    RecipientAlter_tmp = ontology.rovRegisteredOrganization(uri=None, imposeURI=Recipient_tmp.getInstanceUri())
                    RecipientAlter_tmp.rovlegalName += row['LE_NAME']
                    RecipientAlter_tmp.rovregistration += row['LE_VAT']
                    RecipientAlter_tmp.rovorgType += row['LEGAL_FORM_CD'] + ', ' + row['LEGAL_FORM_DESC']
                elif recipientCatg[row['LE_ACCOUNT_GROUP_DESC'].casefold()] == "International Organisation":
                    RecipientAlter_tmp = ontology.InternationalOrganisation(uri=None, imposeURI=Recipient_tmp.getInstanceUri())
                    # RecipientAlter_tmp.prefLabel += row['LE_NAME']
                elif recipientCatg[row['LE_ACCOUNT_GROUP_DESC'].casefold()] == "Trust Fund":
                    RecipientAlter_tmp = ontology.TrustFund(uri=None, imposeURI=Recipient_tmp.getInstanceUri())
                    # RecipientAlter_tmp.prefLabel += row['LE_NAME']
                elif recipientCatg[row['LE_ACCOUNT_GROUP_DESC'].casefold()] == "NFPO":
                    RecipientAlter_tmp = ontology.NonProfitOrganisation(uri=None, imposeURI=Recipient_tmp.getInstanceUri())
                    # RecipientAlter_tmp.prefLabel += row['LE_NAME']
                    RecipientAlter_tmp.rovregistration += row['LE_VAT']
                    RecipientAlter_tmp.rovorgType += row['LEGAL_FORM_CD'] + ', ' + row['LEGAL_FORM_DESC']
                elif recipientCatg[row['LE_ACCOUNT_GROUP_DESC'].casefold()] == "NGO":
                    RecipientAlter_tmp = ontology.NGO(uri=None, imposeURI=Recipient_tmp.getInstanceUri())
                    # RecipientAlter_tmp.prefLabel += row['LE_NAME']
                    RecipientAlter_tmp.rovregistration += row['LE_VAT']
                    RecipientAlter_tmp.rovorgType += row['LEGAL_FORM_CD'] + ', ' + row['LEGAL_FORM_DESC']
                elif recipientCatg[row['LE_ACCOUNT_GROUP_DESC'].casefold()] == "Person":
                    RecipientAlter_tmp = ontology.cpovPublicOrganisation(uri=None, imposeURI=Recipient_tmp.getInstanceUri())
                    RecipientAlter_tmp.foaffamilyName += row['LE_NAME']
                else:
                    print('Recipient: no additional type match.')

                # -------------------------#
                # Create Legal Commitment #
                # -------------------------#
                lbl = "LegalCommitment" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                LegalCommitment_tmp = ontology.LegalCommitment(uri=URISpec)
                LegalCommitment_tmp.label += row['GRANT_SUBJECT'] # to check, should be subject
                LegalCommitment_tmp.fundingType += row['LC_TYPE']
                LegalCommitment_tmp.hasCoordinator += Recipient_tmp

                # -----------------------------#
                # Create Budgetary  Commitment #
                # -----------------------------#
                lbl = "BudgetaryCommitment" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                BudgetaryCommitment_tmp = ontology.BudgetaryCommitment(uri=URISpec)
                # create positionKey
                # lbl = "positionKey" + str(ix)
                # URISpec = URISpecification(def_base_uri,{"label":lbl})
                # tmp = ontology.admsIdentifier(uri=URISpec)
                # BudgetaryCommitment_tmp.positionKey += tmp
                # BudgetaryCommitment_tmp.commitmentKey += row['COM_HD_KEY']
                BudgetaryCommitment_tmp.hasLegalCommitment += LegalCommitment_tmp
                # BudgetaryCommitment_tmp.date += row['BL_YEAR']

                # ----------------------#
                # Create Monetary Value # --> link to EU Budget
                # ----------------------#
                lbl = "MonetaryValue" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                MonetaryValue_tmp = ontology.MonetaryValue(uri=URISpec)
                MonetaryValue_tmp.value += row['AMNT']
                # MonetaryValue_tmp.currency += row['AMNT'] # values from controlled voc

                # ------------------------------#
                # Create Indicative Transaction #
                # ------------------------------#
                lbl = "IndicativeTransaction" + str(ix)
                URISpec = URISpecification(def_base_uri,{"label":lbl})
                IndicativeTransaction_tmp = ontology.IndicativeTransaction(uri=URISpec)
                IndicativeTransaction_tmp.committedTo += Recipient_tmp
                # IndicativeTransaction_tmp.committedBy += row['DG_CD'] # must be skos:Concept
                IndicativeTransaction_tmp.hasEstimatedValue += MonetaryValue_tmp

        print('\t\t\t\t\t ... Done.')

    # URISpec = URISpecification(def_base_uri,{"label":"BudgetaryCommitment"})
    # BudgetaryCommitment1 = ontology.BudgetaryCommitment(uri=URISpec, label="BudgetaryCommitment", comment="BudgetaryCommitment")
    #
    # URISpec = URISpecification(def_base_uri,{"label":"MonetaryValueLabel"})
    # MonetaryValue1 = ontology.MonetaryValue(uri=URISpec, label="MonetaryValueLabel", comment="MonetaryValueComment")
    #
    # URISpec = URISpecification(def_base_uri,{"label":"LegalCommitmentLabel"})
    # LegalCommitment1 = ontology.LegalCommitment(uri=URISpec, label="LegalCommitmentLabel", comment="LegalCommitmentComment")
    #
    # URISpec = URISpecification(def_base_uri,{"label":"IndicativeTransactionLabel"})
    # IndicativeTransaction1 = ontology.IndicativeTransaction(uri=URISpec, label="IndicativeTransactionLabel", comment="IndicativeTransactionComment")
    #
    # IndicativeTransaction2 = eval("ontology." + recipientCatg["EIB"] + '(uri=URISpec, label="IndicativeTransaction2Label", comment="IndicativeTransaction2Comment")')
    #
    # URISpec = URISpecification(def_base_uri,{"label":"RecipientLabel"})
    # Recipient1 = ontology.Recipient(uri=URISpec, label="RecipientLabel", comment="RecipientComment")
    # RegisterdOrganisation = ontology.rovRegisteredOrganization(uri=None, label="RegisterdOrganisationLabel", comment="RegisterdOrganisationComment", imposeURI=Recipient1.getInstanceUri())
    #
    # IndicativeTransaction1.hasEstimatedValue += MonetaryValue1
    # BudgetaryCommitment1.hasTotalValue += MonetaryValue1
    # BudgetaryCommitment1.hasLegalCommitment += LegalCommitment1
    # BudgetaryCommitment1.hasIndicativeTransaction += IndicativeTransaction1
    # LegalCommitment1.hasCoordinator += Recipient1
    # IndicativeTransaction1.committedTo += Recipient1
    # MonetaryValue1.value += 2000
    # MonetaryValue1.currency += "http://EUR"
    # IndicativeTransaction1.committedBy += "http://wowowo"

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
