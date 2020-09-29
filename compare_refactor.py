import os
import MySQLdb
import pandas as pd
import pdb
import os
from tqdm import tqdm

ec2_params = {
	"host":"ec2-54-68-171-132.us-west-2.compute.amazonaws.com",
	"current":"childes_db_dev",
	"supported": ["2018.1","2019.1","2020.1", "childes_db_dev"],
	"historical":[],
	"user": "childesdb",
	"password": os.environ['CHILDES_EC2_PASS'] #TODO make this a path variable
}

local_params = {
    "host": "127.0.0.1",
    "current":"childes_db_dev",
	"supported": ["2018.1","2019.1","2020.1", "childes_db_dev"],
	"historical":[],
    "user": "root",
    "password": os.environ['ROOT_PASS']
}

#Counters for when both Chompsky and EC2 match
passed_utt = 0
passed_token = 0
mismatched_utts = []
mismatched_tokens = []

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

def query_hash(con, query, transcript_id, column_format):
    """
    Inputs:
    For a particular version of the database (specified in con), converts data corresponding to a specific transcript to a hashed form.
    Each row is hashed to a single value and the rows are placed in a Pandas series
    """
    fmt_query = query % transcript_id
    query_result = pd.read_sql(fmt_query, con)
    query_result = query_result[column_format]
    return pd.util.hash_pandas_object(query_result)

def compare_transcripts(ec2_con, local_con, ec2_id, local_id, token_fmt, utt_fmt):
    """
    At the token and utterance level, compares a transcript on the EC2 instance to the version on Chompsky.
    token_fmt and utt_fmt are the column order on the EC2 instance.
    """
    token_query = "SELECT * FROM token WHERE transcript_id = %s"
    utt_query = "SELECT * FROM utterance WHERE transcript_id = %s"
    try:
        global passed_utt
        assert all(query_hash(ec2_con, utt_query, ec2_id, utt_fmt) == query_hash(local_con, utt_query, local_id, utt_fmt))
        passed_utt += 1
    except:
        global mismatched_utts
        mismatched_utts.append({'ec2_id': ec2_id, 'local_id': local_id})
    try:
        global passed_token
        assert all(query_hash(ec2_con, token_query, ec2_id, token_fmt) == query_hash(local_con, token_query, local_id, token_fmt))
        passed_token += 1
    except:
        global mismatched_tokens
        mismatched_tokens.append({'ec2_id': ec2_id, 'local_id': local_id})
    

if __name__ == "__main__":
    ec2_con = connect_to_childes(db_args = ec2_params)
    local_con = connect_to_childes(db_args = local_params)

    transcript_query = "SELECT id, filename FROM transcript"
    ec2_transcripts = pd.read_sql(transcript_query, ec2_con)
    local_transcripts = pd.read_sql(transcript_query, local_con)

    #Output should be a DF with local transcript ID, EC2 transcript ID, and filename.
    id_map = local_transcripts.merge(ec2_transcripts, on = 'filename', how = 'inner', suffixes = ['_local', '_ec2'])

    """
    In order to see if the version on Chompsky is consistent with EC2, we need to have a consistent set of columns.
    Some additions have been made to the current version of Childes DB (i.e. dependency parse columns), and IDs may be 
    inconsistent across machines.
    """
    strip_id_cols = lambda cols: [c for c in cols if not c.endswith('id')] #Getting rid of the 
    ec2_token_cols = strip_id_cols(pd.read_sql("SELECT * FROM token WHERE 1 = 0", ec2_con).columns)
    ec2_utt_cols = strip_id_cols(pd.read_sql("SELECT * FROM utterance WHERE 1 = 0", ec2_con).columns)

    for index, row in tqdm(id_map.iterrows(), total = id_map.shape[0]):
        local_tid, ec2_tid = row['id_local'], row['id_ec2']
        compare_transcripts(ec2_con, local_con, ec2_tid, local_tid, ec2_token_cols, ec2_utt_cols)

        print("Token-Level: %s of %s transcripts match" % (passed_token, index + 1))
        print("Utterance-Level: %s of %s transcripts match" % (passed_utt, index + 1))

        if index % 100 == 0: #logging the IDs of transcripts that didn't match on EC2 and Chompsky
            pd.DataFrame(mismatched_tokens).to_csv('token_errors.log', index = False)
            pd.DataFrame(mismatched_utts).to_csv('utt_errors.log', index = False)

    pd.DataFrame(mismatched_tokens).to_csv('token_errors.log', index = False)
    pd.DataFrame(mismatched_utts).to_csv('utt_errors.log', index = False)