import os
from django.core.management import BaseCommand
import time

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--data_source', help='Name of the data source, eg CHILDES or PhonBank')
        parser.add_argument('--selected_collection', help='Name of collection (e.g. Eng-NA, Spanish) to process. If unspecified, will process all')
        parser.add_argument('--corpus_name', help='Name of the data corpus, eg Providence or Manchester')
        parser.add_argument('--xml_dir', help='Directory where transcript is contained')
        parser.add_argument('--fileid', help='File name ending in .xml')

    def handle(self, *args, **options):
        #import pdb
        #pdb.set_trace()
        self.test_single_transcript(options['selected_collection'], options['data_source'], options['corpus_name'], options['fileid'], options['xml_dir'])

    def test_single_transcript(self, collection_name, data_source, corpus_name, fileid, dir_with_xml):
        from db.childes_db import process_file
        from db.childes import CHILDESCorpusReader
        from db.models import Corpus, Collection
        
        # collection name, data source, corpus name, fileid, dir_with_xml
        collection = Collection.objects.create(name=collection_name, data_source = data_source)
        corpus = Corpus.objects.create(name=corpus_name, collection=collection, collection_name=collection.name, data_source = data_source)
        nltk_corpus = CHILDESCorpusReader(dir_with_xml, '.*.xml')
        process_file(fileid, dir_with_xml, corpus, collection, nltk_corpus, None)  # no pid dict
