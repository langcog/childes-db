import os
import time
import datetime
import json
#i#i#import config
import wget
import subprocess
import argparse
import numpy as np

# download and unzip the directory structure that can be used as the input for the populate_db management command

# example invocation: python3 download_corpora.py --versions_root /shared_hd2/childes-db-xml --version 2020.1 

parser = argparse.ArgumentParser()
parser.add_argument("--versions_root", help='root to place all updates')
parser.add_argument("--version", help='version string for the new dataset')
args = parser.parse_args()

# set up some paths and directories
paths = {}
paths['versions_root'] = args.versions_root
paths['version'] = os.path.join(args.versions_root, args.version)
paths['candidate'] = os.path.join(args.versions_root, args.version,'candidate')
paths['logs'] = os.path.join(args.versions_root, args.version,'logs')

for dir_path in paths.values():
	if not os.path.exists(dir_path):  
		os.makedirs(dir_path)

paths['wget_log'] = os.path.join(paths['logs'],'wget.log')


base_urls = ["https://childes.talkbank.org/data-xml/", "https://phonbank.talkbank.org/data-xml/"]

for base_url in base_urls:

	print('Downloading zip files with xml transcripts from '+base_url+'...')
	wget_command = "wget -N -r -np -A.zip -o "+paths['wget_log']+" -e robots=off " + base_url	
	# -N checks for server-side changes and does not download if no changes
	# -r looks recursive
	# -np no parent
	# -A.zip limits to zip files
	# -e robots=off: disregards robots.txt

	try:
		os.system('cd '+ paths['candidate'] +' && ' + wget_command)

		# parse the output to wget to see if anything has changed
		wget_responses = wget.parse_wget_output(paths['wget_log'])
	except Exception as e:
		print('Problem with downloading....')
		print(e)
		#email.alert(subject=download_failure_subject_message, log_path)	

zipfiles = []
dirs_with_zipfiles = []
for root, dirs, files in os.walk(paths['candidate']):
    for file in files:
        if file.endswith(".zip"):
        	zipfiles.append(os.path.join(root, file))
        	dirs_with_zipfiles.append(root)

print('Leaving zipfile placeholders...')
for zipfile in zipfiles:
	make_placeholder_command = "touch "+zipfile+"_placeholder" 
	os.system(make_placeholder_command)

print('Unzipping the zip files...')
dirs_with_zipfiles = np.unique(dirs_with_zipfiles) # avoid redundancy
for dir_with_zipfiles in dirs_with_zipfiles:
	unzip_command = "cd "+ dir_with_zipfiles +" && unzip '*.zip' && rm *.zip"	
	os.system(unzip_command)

print('Complete!')

# merge these two together? or just process in this directory structure

#new_data_dir = os.path.join(paths['candidate'], 'childes.talkbank.org/data-xml')

#print('After migrating (`python manage.py makemigrations`; `python manage.py migrate`), you are ready to run `python migrate.py populate_db` from djangoapp, after updating DATA_XML_PATH in config.JSON to point to '+new_data_dir)	
	
	
	



	
