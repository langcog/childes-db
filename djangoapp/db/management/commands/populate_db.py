from django.core.management import BaseCommand

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "My test command"

    def add_arguments(self, parser):
        parser.add_argument('--collection', help='Name of collection (e.g. Eng-NA, Spanish)')
        parser.add_argument('--path', help='Path to collection')

    # A command must define handle()
    def handle(self, *args, **options):
        from db.childes_db import populate_db

        collection = options.get("collection")
        path = options.get("path")

        if not collection:
            self.stdout.write("Missing --collection argument")
            return

        if not path:
            self.stdout.write("Missing --path argument")
            return

        populate_db(collection, path)