import os
import MySQLdb
import sqlalchemy

params = {
	"host":"ec2-54-68-171-132.us-west-2.compute.amazonaws.com",
	"current":"childes_db_dev",
	"supported": ["2018.1","2019.1","2020.1", "childes_db_dev"],
	"historical":[],
	"user": "childesdb",
	"password": "uy5z4hf7ihBjf"
}

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

db = connect_to_childes(db_args = params)
#Pull data from the utterances table and join it with the transcripts table to get the path to the right file
query = "SELECT gloss, utterance.language, actual_phonology, model_phonology, filename, transcript_id FROM utterance JOIN transcript ON utterance.transcript_id = transcript.id WHERE actual_phonology <> '' AND model_phonology <> ''"
print("Running query to childes-db")
cursor = db.cursor()
cursor.execute(query)
print("Number of rows in query result: " + str(cursor.rowcount))
cursor.close()
db.close()
