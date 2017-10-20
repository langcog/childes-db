import os
from django.conf import settings
from django.core.management import BaseCommand

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "My test command"

    def add_arguments(self, parser):
        parser.add_argument('--collection', help='Name of collection (e.g. Eng-NA, Spanish)')

    # A command must define handle()
    def handle(self, *args, **options):
        from db.childes_db import populate_db

        collection = options.get("collection")

        if collection:
            populate_db(os.path.join(settings.DATA_XML_PATH, collection))
        else:
            # Import all collections
            for collection in os.walk(settings.DATA_XML_PATH).next()[1]:
                populate_db(os.path.join(settings.DATA_XML_PATH, collection))