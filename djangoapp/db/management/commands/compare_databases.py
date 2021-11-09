# example invocation: python3 manage.py compare_databases --old_db_name 2020.1  --new_db_name childes_db_dev_test2

from django.core.management import BaseCommand
import os
import MySQLdb
import pandas as pd
import numpy as np
import pdb
import os
from tqdm import tqdm

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

def compare_hashes(old_transcript_id, new_transcript_id, new_db_con, old_db_con, query):    	
    '''compare hashes for records in two transcripts; now deprecated in favor of compare_transcripts'''
    old_hash = pd.DataFrame({'old_hash' : query_hash(old_db_con, query, old_transcript_id)})
    new_hash = pd.DataFrame({'new_hash':query_hash(new_db_con, query, new_transcript_id)})    
    df_merged = new_hash.merge(old_hash, how='outer', left_index=True, right_index=True)
    
    df_merged['equal'] = df_merged.old_hash.eq(df_merged.new_hash)  
    return(df_merged.loc[~df_merged.equal])

def run_query(con, query, transcript_id, drop_id_cols):
    '''Reusable base function for running a query through Pandas and returning a DF'''
    fmt_query = query % transcript_id
    query_result = pd.read_sql(fmt_query, con)    
    if drop_id_cols:
        dropcols = [c for c in query_result.columns if c.endswith('id')]
        query_result = query_result.drop(dropcols, axis=1)
    return(query_result)

def compare_dfs(old_transcript_id, new_transcript_id, old_db_con, new_db_con,  query, return_type = "df"):
    '''Find columns with differences between two dataframes; now deprecated in favor of compare_transcripts'''
    old_db_df = run_query(old_db_con, query, old_transcript_id, drop_id_cols=True)
    new_db_df = run_query(new_db_con, query, new_transcript_id, drop_id_cols=True)    
    old_db_df.sort_index(inplace=True)
    new_db_df.sort_index(inplace=True)
    try:
        comparison_df = new_db_df.compare(old_db_df)

        if return_type == 'df':
            return({'comparison_df': comparison_df})
        elif return_type == "colnames":
            return(np.unique(comparison_df.columns.get_level_values(0)))        
    except:        
        return({'old_table': old_db_df, 'new_table': new_db_df}) 
    
    

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Check how two databases differ by looking at the transcripts"

    def add_arguments(self, parser):
        parser.add_argument('--old_db_name', help='Name of the old database')
        parser.add_argument('--new_db_name', help='Name of the new database')
        
    # A command must define handle()
    def handle(self, *args, **options):

        old_db_name = options.get("old_db_name")
        new_db_name = options.get("new_db_name")

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

        old_db_con = connect_to_childes(db_version = old_db_name, db_args = local_params)
        new_db_con = connect_to_childes(db_version = new_db_name, db_args = local_params)
        transcript_query = "SELECT id, filename FROM transcript"
        old_transcripts = pd.read_sql(transcript_query, old_db_con)
        new_transcripts = pd.read_sql(transcript_query, new_db_con)

        #Output should be a DF with local transcript ID, EC2 transcript ID, and filename.
        id_map = new_transcripts.merge(old_transcripts, on = 'filename', how = 'outer', suffixes = ['_new', '_old'])    
    
        
        in_new_but_not_old = id_map.loc[id_map.id_old.isna()]
        in_old_but_not_new = id_map.loc[id_map.id_new.isna()]
        
        print(str(len(in_new_but_not_old)) + " transcripts from the new database were not present in the old database")
        print(str(len(in_old_but_not_new)) + " transcripts from old database were not present in the new database")        

        # initialize directories that aren't
        os.system("mkdir -p utt_mismatch_csvs")
        os.system("mkdir -p token_mismatch_csvs")

        transcript_results = [] 
        for index, row in tqdm(id_map.iterrows(), total = id_map.shape[0]):     

            if np.isnan(row['id_old']) or np.isnan(row['id_new']):
                # one of the transcripts is missing
                                
                tokens_passed = None
                utts_passed = None
                
            else:
                # first, check if the utts match up at the transcript level:        
                utt_query = "SELECT * FROM utterance WHERE transcript_id = %s"
                utt_hash_mismatch = compare_hashes(row['id_old'], row['id_new'], new_db_con, old_db_con,  utt_query)
                if len(utt_hash_mismatch) > 0:
                    utts_passed = False
                    utt_comparison = compare_dfs(row['id_old'], row['id_new'], old_db_con, new_db_con,  utt_query, "df")

                    if 'comparison_df' in utt_comparison.keys():
                        # if there are the same number of records, use the comparison function
                        utt_comparison['comparison_df'].to_csv(os.path.join('utt_mismatch_csvs', row['filename'].replace('.xml','.csv').replace('/','_')), index = False)

                    else:
                        # if there is a different number of records, then write out the datasets separately
                        utt_comparison['old_table'].to_csv(os.path.join('utt_mismatch_csvs', row['filename'].replace('.xml','_old.csv').replace('/','_')), index = False)

                        utt_comparison['new_table'].to_csv(os.path.join('utt_mismatch_csvs', row['filename'].replace('.xml','_new.csv').replace('/','_')), index = False)

                        
                else:
                    utts_passed = True

                # then check if the tokens match up at the transcript level: 
                token_query = "SELECT * FROM token WHERE transcript_id = %s"
                token_hash_mismatch = compare_hashes(row['id_old'], row['id_new'], new_db_con, old_db_con,  token_query)
                if len(token_hash_mismatch) > 0:
                    tokens_passed = False
                    token_comparison = compare_dfs(row['id_old'], row['id_new'], old_db_con, new_db_con,  token_query, "df")

                    if 'comparison_df' in token_comparison.keys():
                        # if there are the same number of records, use the comparison function
                        token_comparison['comparison_df'].to_csv(os.path.join('token_mismatch_csvs', row['filename'].replace('.xml','.csv').replace('/','_')), index = False)

                    else:
                        # if there is a different number of records, then write out the datasets separately

                        token_comparison['old_table'].to_csv(os.path.join('token_mismatch_csvs', row['filename'].replace('.xml','_old.csv').replace('/','_')), index = False)

                        token_comparison['new_table'].to_csv(os.path.join('token_mismatch_csvs', row['filename'].replace('.xml','_new.csv').replace('/','_')), index = False)


                else:
                    tokens_passed = True

            # keep a record for this specific transcript            
            
            transcript_results.append(
                {'filename': row['filename'],
                'old_transcript_id': row['id_old'], 
                'new_transcript_id': row['id_new'],
                'utts_passed': utts_passed,
                'tokens_passed': tokens_passed,                
                }
            )

        # write out all of the transcriot records
        tr_df = pd.DataFrame(transcript_results)
        tr_df.to_csv("transcript_checks.csv", index=False)       
