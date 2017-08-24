import config
import os

def alert(subject, log_path):
	with open(log_path, 'r') as content_file:
		log_body = content_file.read()	

	#log_body = "CHILDES-db has been regenerated" 

	for address in config.alert_addresses:
		email_command = "echo '"+ log_body +"' | mail -s "+subject+" meylan.stephan@gmail.com"
		os.system(email_command)