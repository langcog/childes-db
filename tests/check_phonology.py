import os
import MySQLdb
import pandas as pd

params = {
	"host":"ec2-54-68-171-132.us-west-2.compute.amazonaws.com",
	"current":"childes_db_dev",
	"supported": ["2018.1","2019.1","2020.1", "childes_db_dev"],
	"historical":[],
	"user": "childesdb",
	"password": "uy5z4hf7ihBjf"
}

#Number of rows that we sample
sample_size = 2

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
                    db = db_args['current'])
    return childes_con


def parse_xml(row, u_index):
    """
    Read XML file from the row, and return the actual IPA and model IPA
    """

def log_error(row, exception):
    """
    Save error in logs
    """
db = connect_to_childes(db_args = params)
#Pull data from the utterances table and join it with the transcripts table to get the path to the right file
query = "SELECT utterance.id, gloss, utterance.language, actual_phonology, model_phonology, utterance_order, filename \
FROM utterance JOIN transcript ON utterance.transcript_id = transcript.id \
WHERE actual_phonology <> '' AND model_phonology <> ''"

print("Running query to childes-db")
df = pd.read_sql(query, db)
db.close()

df = df.sample(sample_size)

for r in df.iterrows():
    parsed_actual, parsed_model = parse_xml(row)
    db_actual, db_model = r['actual_phonology'], r['model_phonology']
    try:
        assert parsed_actual == db_actual
        assert parsed_model == db_model
    except:
        log_error(row, exception)