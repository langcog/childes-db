import os
from django.core.management import BaseCommand

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Populate childes-db through Django"

    def add_arguments(self, parser):
        parser.add_argument('--collection_root', help='Path to the collection(s) to process')
        parser.add_argument('--collection', help='Name of collection (e.g. Eng-NA, Spanish) to process. If unspecified, will process all')
        parser.add_argument('--data_source', help='Name of the data source, eg CHILDES or PhonBank')

    # A command must define handle()
    def handle(self, *args, **options):

        from db.childes_db import populate_db        

        collection_root = options.get("collection_root")
        collection = options.get("collection")
        data_source = options.get("data_source")

        populate_db(collection_root, data_source, collection)

        