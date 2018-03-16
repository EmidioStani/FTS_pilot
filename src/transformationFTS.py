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

    if False:
        print("List of all terms detected:")
        for term in ontology.__terms__:
            print(term)
        print('')

    #-------------------------------#
    # Create Sample Dataset         #
    #-------------------------------#

    # Load Recipient Categorisation dictionary
    recipientCatg = config_data['recipientCatg']

    URISpec = URISpecification(def_base_uri,{"label":"BudgetaryCommitment"})
    BudgetaryCommitment1 = ontology.BudgetaryCommitment(uri=URISpec, label="BudgetaryCommitment", comment="BudgetaryCommitment")

    URISpec = URISpecification(def_base_uri,{"label":"MonetaryValueLabel"})
    MonetaryValue1 = ontology.MonetaryValue(uri=URISpec, label="MonetaryValueLabel", comment="MonetaryValueComment")

    URISpec = URISpecification(def_base_uri,{"label":"LegalCommitmentLabel"})
    LegalCommitment1 = ontology.LegalCommitment(uri=URISpec, label="LegalCommitmentLabel", comment="LegalCommitmentComment")

    URISpec = URISpecification(def_base_uri,{"label":"IndicativeTransactionLabel"})
    IndicativeTransaction1 = ontology.IndicativeTransaction(uri=URISpec, label="IndicativeTransactionLabel", comment="IndicativeTransactionComment")

    IndicativeTransaction2 = eval("ontology." + recipientCatg["EIB"] + '(uri=URISpec, label="IndicativeTransaction2Label", comment="IndicativeTransaction2Comment")')

    URISpec = URISpecification(def_base_uri,{"label":"RecipientLabel"})
    Recipient1 = ontology.Recipient(uri=URISpec, label="RecipientLabel", comment="RecipientComment")
    RegisterdOrganisation = ontology.rovRegisteredOrganization(uri=None, label="RegisterdOrganisationLabel", comment="RegisterdOrganisationComment", imposeURI=Recipient1.getInstanceUri())

    IndicativeTransaction1.hasEstimatedValue += MonetaryValue1
    BudgetaryCommitment1.hasTotalValue += MonetaryValue1
    BudgetaryCommitment1.hasLegalCommitment += LegalCommitment1
    BudgetaryCommitment1.hasIndicativeTransaction += IndicativeTransaction1
    LegalCommitment1.hasCoordinator += Recipient1
    IndicativeTransaction1.committedTo += Recipient1
    MonetaryValue1.value += 2000
    MonetaryValue1.currency += "http://EUR"
    IndicativeTransaction1.committedBy += "http://wowowo"

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

    total_number = [1,1,1,1,1]
    with click.progressbar(total_number) as total:
        for count in total:
            time.sleep(0.2)

def read_csv(filename, columns):
    df = pandas.read_csv(filename, sep=',', encoding = "ANSI", quotechar='"')#, names=columns)
    data = df.values
    # print(df['AMNT'])
    # print(data[19,:]) # some tricky lines to do a sanity check
    # print(data[23433,:])
    return data

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
