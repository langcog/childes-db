from django import db
from django.core.management import BaseCommand

class Command(BaseCommand):
    help = "Drops all tables in childes-db"

    def handle(self, *args, **options):
        cursor = db.connection.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        cursor.execute(
            "SELECT concat('DROP TABLE IF EXISTS ', table_name, ';') "
            "FROM information_schema.tables "
            "WHERE table_schema = 'childesdb';"
        )

        for query in cursor.fetchall():
            cursor.execute(query[0])

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")