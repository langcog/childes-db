import os
from django.core.management import BaseCommand
import time

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--data_source', help='Name of the data source, eg CHILDES or PhonBank')
        parser.add_argument('--collection_root', help='Path to the collection(s) to process')
        parser.add_argument('--selected_collection', help='Name of collection (e.g. Eng-NA, Spanish) to process. If unspecified, will process all')
        parser.add_argument('--corpus', help='Name of the data corpus, eg Providence or Manchester')

    def handle(self, *args, **options):
        #import pdb
        #pdb.set_trace()
        self.test_single_corpus(options['collection_root'], options['corpus'], options['data_source'], options['selected_collection'])

    def test_single_corpus(self, collection_root, selected_corpus, data_source, selected_collection):
        from db.childes_db import process_collection
        from db.utils import flatten_list
        single_corpus_start_time = time.time()
        results = []

        pool = None
        pid_dict = {}

        results.append(process_collection(collection_root, selected_collection, data_source, pool, pid_dict, parallelize=False, selected_corpora = [selected_corpus]))

        print('Results:') # this is where error messages should be caught    
        flat_results = flatten_list(results)    
        print(flat_results)
    
        print('Finished processing single corpus in '+str(round((time.time() - single_corpus_start_time) / 60., 3))+' minutes')

