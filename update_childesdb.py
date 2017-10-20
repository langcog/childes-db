# running on a cron job on Lovelace:
import os
#os.chdir('/home/stephan/notebooks/childes-db')
import time
import datetime
import json

import email_notifications
import config
import wget
reload(config)
import subprocess

date = datetime.datetime.now().strftime("%Y-%m-%d")

for collection in config.collections:
	#collection = config.collections[0]	
	new_db_name = 'childes-db_'+collection+'_'+date	
	print('Generating '+new_db_name)

	#print('Generating path structure...')
	if not os.path.isdir(os.path.join(config.version_dir, collection)):
		os.mkdir(os.path.join(config.version_dir, collection))
	collection_version_dir = os.path.join(config.version_dir, collection, date)
	if not os.path.isdir(collection_version_dir):
		os.mkdir(collection_version_dir)	
	
	# collection_candidate_dir = os.path.join(config.candidate_dir, collection)
	# if not os.path.isdir(collection_candidate_dir):
	# 	os.mkdir(collection_candidate_dir)
	log_path = os.path.join(collection_version_dir,'log')
	if not os.path.isdir(log_path):
		os.mkdir(log_path)
	wget_log_path = os.path.join(log_path, 'wget.log')		

	collection_url = config.xml_url + collection + '/'

	print('Updating local copy ("candidate") from CHILDES')
	os.chdir(config.candidate_dir)

	wget_command = "wget -N -r -np -A.zip -o "+wget_log_path+" -e robots=off " + collection_url	
	try:
		os.system('cd '+ config.candidate_dir +' && ' + wget_command)

		# parse the output to wget to see if anything has changed
		wget_responses = wget.parse_wget_output(wget_log_path)
	except:
		#email.alert(subject=download_failure_subject_message, log_path)	

	if len(wget_responses) == 0 and not config.forceUpdate:
		print('None of the transcripts have changed. Sending and email.')
		#email.alert(subject=noop_subject_message,log_path='!!!')
	else:	
		if forceUpdate:
			print('Regenerating because forceUpdate is set to true in the configuration file')
		else:	
			print('At least one of the transcripts has changed, updating the database...')

		try:						
			print('Copying from candidate to version directory')
			copy_command = 'cp '+config.candidate_dir+'/childes.talkbank.org/data-xml/'+collection+'/* ' + collection_version_dir
			os.system(copy_command)
			
			print('Unzipping in version directory')
			unzip_command = "cd "+ collection_version_dir +" && unzip '*.zip' && rm *.zip"
			os.system(unzip_command)
			
			migrate_log = os.path.join(log_path, 'migrate.log')
					
			# update the Django settings JSON so that the migration will connect to a new database

			config_json_path = os.path.join(config.code_dir, 'djangoapp', 'config.json')
			with open(config_json_path) as json_data:
    			config_json = json.load(json_data)	


    		config_json['mysql']['DB_NAME']= new_db_name	

    		with open(config_json_path, 'w') as outfile:
    			json.dump(config_json, outfile)

			# requires subprocess to activate the venv
			subprocess.Popen([os.path.join(config.code_dir, "childesdb/bin/python"), os.path.join(config.code_dir, 'djangoapp',"manage.py"), "migrate", "--collection", collection, "--path", collection_version_dir])
	
			#!!! this fails	

			#then propagate this to the remote machine; need to have SSH + EC2 credentials
			# could create a new instance through the EC2 CLI
			# get it to the production database
			# see Boto

			# do a remote sql dump into the Apache version running on the remote
			remote_serve_collection_dir = os.path.join(remote_serve_dir, collection version)
			#dump_command = 'sqldump #name# > ' + remote_serve_collection_dir
			#!!! or this is a remote command to dump and upload to S3 or Glacier
			os.system(dump_command)

			#email.alert(subject=success_subject_message, log_path)
		except: 
			#email.alert(subject=processing_failure_subject_message, log_path)
			pass