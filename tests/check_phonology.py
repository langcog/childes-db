import os
import MySQLdb
import pandas as pd
from nltk.corpus.reader.xmldocs import ElementTree
from tqdm import tqdm

params = {
	"host":"ec2-54-68-171-132.us-west-2.compute.amazonaws.com",
	"current":"childes_db_dev",
	"supported": ["2018.1","2019.1","2020.1", "childes_db_dev"],
	"historical":[],
	"user": "childesdb",
	"password": "uy5z4hf7ihBjf"
}

#Number of rows that we sample
sample_size = 10

def connect_to_childes(db_version = 'current', db_args = None):
    """Connects to childes-db
    Args:
        db_version: String of the name of the database version to use
        db_args: Dict with host, user, and password defined
    Returns:
        A MySQLdb connection object for the CHILDES database
    """
    childes_con = MySQLdb.connect(
                    host = db_args['host'],
                    #port = db_args['port'], #no port specified in json?
                    user = db_args['user'],
                    passwd = db_args['password'],
                    db = db_args['current'],
                    use_unicode = True,
                    charset = 'utf8')
    return childes_con


def parse_xml(xml_path, u_index):
    """
    Read XML file from the row, and return the actual IPA and model IPA
    Args: 
        xml_path: filename in childes-db, path to XML with this utterance
        u_index: utterance_order in childes-db, represents the index of this utterance
    Returns:
        two strings which should correspond to actual_phonology and model_phonology for this utterance 
    """
    NS = 'http://www.talkbank.org/ns/talkbank' #resolving namespace issue (from db/childes.py)
    fileid = os.path.join("../../../../", "shared_hd1", "childes-db-xml", xml_path) #FIXME: change to absolute path
    tree = ElementTree.parse(fileid)
    xmldoc = tree.getroot()

    uid = 'u' + str(u_index - 1)
    './/{%s}u[@uID="u2"]'
    xmlsent = xmldoc.find('.//{%s}u' % NS + '[@uID="' + uid + '"]')
    actual_words = xmlsent.findall('.//{%s}pg/{%s}actual/{%s}pw' % (NS, NS, NS))
    model_words = xmlsent.findall('.//{%s}pg/{%s}model/{%s}pw' % (NS, NS, NS))

    actual_pho =  [''.join([x.text for x in y.findall('{%s}ph' % NS)]) for y in actual_words]
    model_pho =  [''.join([x.text for x in y.findall('{%s}ph' % NS)]) for y in model_words]
    actual_pho, model_pho = ' '.join(actual_pho), ' '.join(model_pho)
    return actual_pho.encode('utf8'), model_pho.encode('utf8')
    
def log_error(index, row, exception):
    """
    Save error in logs
    Index is the row which the error occurred in
    row contains the data, and exception is an Exception object passed from the try-catch block. These are all cast
    to strings and logged in a file called failed_tests.log
    """
    error_str = "Error at Row " + str(index) + "of query result"
    row_str = str(row)
    exception_str = str(exception)
    log_msg = '\n'.join([error_str, row_str, exception_str])
    with open('failed_tests.log', 'w') as f:
        f.write(log_msg)

db = connect_to_childes(db_args = params)
#Pull data from the utterances table and join it with the transcripts table to get the path to the right file
query = "SELECT utterance.id, gloss, utterance.language, actual_phonology, model_phonology, utterance_order, filename \
FROM utterance JOIN transcript ON utterance.transcript_id = transcript.id \
WHERE actual_phonology <> '' AND model_phonology <> ''"

print("Running query to childes-db")
df = pd.read_sql(query, db)
db.close()

df = df.sample(sample_size) #Sample a set of rows from the dataframe (we don't want to test all the results)

#counters for passed/failed test cases
passed = 0
failed = 0

for i, r in tqdm(df.iterrows(), total=df.shape[0]):
    print(str(passed) + " tests passed, " + str(failed) + " tests failed")
    parsed_actual, parsed_model = parse_xml(r['filename'], r['utterance_order'])
    db_actual, db_model = r['actual_phonology'], r['model_phonology']
    try:
        passed += 1
        assert parsed_actual.decode('utf8') == db_actual
        assert parsed_model.decode('utf8')== db_model
    except Exception as e:
        failed += 1
        log_error(i, r, e)


