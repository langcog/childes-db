import os
import MySQLdb
import pandas as pd
import numpy as np
import pdb
import os
from tqdm import tqdm

local_params = {
    "host": "127.0.0.1",
    "current":"childes_db_dev",
	"supported": ["childes_db_dev", "childes_db_dev_test2"],
	"historical":[],
    "user": "root",
    "password": os.environ['ROOT_PASS']
}

"""
ec2_params = {
	"host":"ec2-54-68-171-132.us-west-2.compute.amazonaws.com",
	"current":"childes_db_dev",
	"supported": ["2018.1","2019.1","2020.1", "childes_db_dev"],
	"historical":[],
	"user": "childesdb",
	"password": os.environ['CHILDES_EC2_PASS']
}
"""

# Counters for when both versions of the database mmatcch
passed_utt = 0
passed_token = 0
mismatched_utts = []
mismatched_tokens = []

def connect_to_childes(db_version, db_args = None):
    """Connects to childes-db
    Args:
        db_version: String of the name of the database version to use
        db_args: Dict with host, user, and password defined
    Returns:
        A MySQLdb connection object for the CHILDES database
    """
    childes_con = MySQLdb.connect(
                    host = db_args['host'],
                    # port = db_args['port'], #no port specified in json?
                    user = db_args['user'],
                    passwd = db_args['password'],
                    db = db_version,
                    use_unicode = True,
                    charset = 'utf8')
    return childes_con

def query_hash(con, query, transcript_id):
    """
    Inputs:
    For a particular version of the database (specified in con), converts data corresponding to a specific transcript to a hashed form.
    Each row is hashed to a single value and the rows are placed in a Pandas series
    """
    query_result = run_query(con, query, transcript_id, drop_id_cols=True)    
    return pd.util.hash_pandas_object(query_result)

def compare_transcripts(expected_con, actual_con, expected_id, actual_id, expected_name, actual_name):
    """
    At the token and utterance level, compares the same transcript across two versions of DBs.
    token_fmt and utt_fmt are the column order on the EC2 instance.
    """
    token_query = "SELECT * FROM token WHERE transcript_id = %s"
    utt_query = "SELECT * FROM utterance WHERE transcript_id = %s"
    try:
        global passed_utt
        assert all(query_hash(expected_con, utt_query, expected_id, utt_fmt) == query_hash(actual_con, utt_query, actual_id))
        passed_utt += 1
    except:
        global mismatched_utts
        mismatched_utts.append({expected_name: expected_id, actual_name: actual_id})
    try:
        global passed_token
        assert all(query_hash(expected_con, token_query, expected_id, token_fmt) == query_hash(actual_con, token_query, actual_id))
        passed_token += 1
    except:
        global mismatched_tokens
        mismatched_tokens.append({expected_name: expected_id, actual_name: actual_id})
    

if __name__ == "__main__":
    expected_name = "childes_db_dev"
    actual_name = "childes_db_dev_test2"

    expected_con = connect_to_childes(db_version = expected_name, db_args = local_params)
    actual_con = connect_to_childes(db_version = actual_name, db_args = local_params)
    transcript_query = "SELECT id, filename FROM transcript"
    exp_transcripts = pd.read_sql(transcript_query, expected_con)
    actual_transcripts = pd.read_sql(transcript_query, actual_con)

    #Output should be a DF with local transcript ID, EC2 transcript ID, and filename.
    id_map = actual_transcripts.merge(exp_transcripts, on = 'filename', how = 'inner', suffixes = ['_refactor', '_main'])
    print(str(len(actual_transcripts) - len(id_map)) + " transcripts from main branch were excluded in refactor")
    print(str(len(actual_transcripts) - len(id_map)) + " transcripts from refactor branch were excluded in main")


    for index, row in tqdm(id_map.iterrows(), total = id_map.shape[0]):
        refactor_tid, main_tid = row['id_refactor'], row['id_main']
        compare_transcripts(expected_con, actual_con, main_tid, refactor_tid, "main_id", "refactor_id")

        print("Token-Level: %s of %s transcripts match" % (passed_token, index + 1))
        print("Utterance-Level: %s of %s transcripts match" % (passed_utt, index + 1))

        if index % 100 == 0: #logging the IDs of transcripts that didn't match on EC2 and Chompsky
            pd.DataFrame(mismatched_tokens).to_csv('token_errors_refactor.log', index = False)
            pd.DataFrame(mismatched_utts).to_csv('token_errors_refactor.log', index = False)

    pd.DataFrame(mismatched_tokens).to_csv('token_errors_refactor.log', index = False)
    pd.DataFrame(mismatched_utts).to_csv('token_errors_refactor.log', index = False)


def compare_hashes(actual_transcript_id, expected_transcript_id, actual_con, expected_con, query):    	
    '''compare hashes for records in two transcripts'''
    actual_hash = pd.DataFrame({'actual':query_hash(actual_con, query, actual_transcript_id)})
    expected_hash = pd.DataFrame({'expected' : query_hash(expected_con, query, expected_transcript_id)})
    df_merged = actual_hash.merge(expected_hash, how='outer', left_index=True, right_index=True)
    return(df_merged)

def run_query(con, query, transcript_id, drop_id_cols):
    '''Reusable base function for running a query through Pandas and returning a DF'''
    fmt_query = query % transcript_id
    query_result = pd.read_sql(fmt_query, con)    
    if drop_id_cols:
        dropcols = [c for c in query_result.columns if c.endswith('id')]
        query_result = query_result.drop(dropcols, axis=1)
    return(query_result)

def compare_dfs(actual_transcript_id, expected_transcript_id, actual_con, expected_con, query, return_type = "df"):
    '''Find columns with differences between two dataframes'''
    actual_df = run_query(actual_con, query, actual_transcript_id, drop_id_cols=True)
    expected_df = run_query(expected_con, query, expected_transcript_id, drop_id_cols=True)
    comparison_df = actual_df.compare(expected_df)
    if return_type == 'df':
        return(comparison_df)
    elif return_type == "colnames":
        return(np.unique(comparison_df.columns.get_level_values(0)))        
