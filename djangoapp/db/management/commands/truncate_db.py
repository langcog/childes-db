from db.truncate import truncate

from django.core.management import BaseCommand

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Truncates all tables in db"

    # A command must define handle()
    def handle(self, *args, **options):
        truncate()