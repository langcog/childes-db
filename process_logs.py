import pandas as pd 
import MySQLdb
import os
from tqdm import tqdm
from compare_refactor import ec2_params, local_params, connect_to_childes

"""
Going through logs (currently contain EC2 transcript ID and local transcript ID only) so we can add some more useful information:
Local Filepath: so we can check individual files
Collection: so we can test at a smaller scale (had to repopulate the DB twice to fix two bugs)
Empty tables (see empty_table_check): this will tell us if it was an error on our end (data for the transcript is different on
Chompsky and EC2, or if the transcript data isn't on Chompsky), or if we just populated the DB with different data (data on Chompsky but not EC2), 
"""
utterance = pd.read_csv('utt_errors.log')
token = pd.read_csv('token_errors.log')

ec2_con = connect_to_childes(db_args = ec2_params)
local_con = connect_to_childes(db_args = local_params)

def local_fname(row):
    return pd.read_sql("SELECT filename FROM transcript WHERE id = %s" % row['local_id'], local_con).values[0][0]

def collection(row):
    return pd.read_sql("SELECT collection_name FROM transcript WHERE id = %s" % row['local_id'], local_con).values[0][0]

def empty_table_check(row, tbl_name):
    ec2_result = pd.read_sql("SELECT * FROM %s WHERE transcript_id = %s" % (tbl_name, row['ec2_id']), ec2_con)
    local_result = pd.read_sql("SELECT * FROM %s WHERE transcript_id = %s" % (tbl_name, row['local_id']), local_con)
    if ec2_result.empty and local_result.empty:
        return 'both'
    elif ec2_result.empty:
        return 'ec2'
    elif local_result.empty:
        return 'local'
    else:
        return 'neither'


def add_to_logs(df, tbl):
    df['local_fname'] = df.progress_apply(local_fname, axis = 1)
    df['collection'] = df.progress_apply(collection, axis = 1)
    df['empty_for_trnst'] = df.progress_apply(empty_table_check, axis = 1, tbl_name = tbl)
    return df

tqdm.pandas()

utterance = add_to_logs(utterance, 'utterance')
token = add_to_logs(token, 'token')

utterance.to_csv('utt_errors.log', index = False)
token.to_csv('token_errors.log', index = False)
