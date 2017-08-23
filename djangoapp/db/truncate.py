from django import db

def truncate():
    cursor = db.connection.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    cursor.execute("TRUNCATE TABLE token")
    cursor.execute("TRUNCATE TABLE utterance")
    cursor.execute("TRUNCATE TABLE participant")
    cursor.execute("TRUNCATE TABLE transcript")
    cursor.execute("TRUNCATE TABLE corpus")
    cursor.execute("TRUNCATE TABLE collection")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")