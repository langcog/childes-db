import os
import time
import datetime
import json
import config
import wget
import subprocess
import argparse
import numpy as np

# download and unzip the directory structure that can be used as the input for the populate_db management command
# version_dir: root of the new CHILDES tree
# version_dir/candidate: root for the XML files
# version_dir/logs: logs for the pre-processing

# example invocation: python update_childesdb.py --versions_root /shared_hd2/childes-db-xml --version 2019.1 --base_url https://childes.talkbank.org/data-xml/

parser = argparse.ArgumentParser()
parser.add_argument("--versions_root", help='root to place all updates')
parser.add_argument("--version", help='version string for the new dataset')
parser.add_argument("--base_url", help='URL of the xml root directory from CHILDES')
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



print('Downloading zip files with xml transcripts from the CHILDES website...')
wget_command = "wget -N -r -np -A.zip -o "+paths['wget_log']+" -e robots=off " + args.base_url	
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


print('Unzipping the zip files...')

dirs_with_zipfiles = []
for root, dirs, files in os.walk(paths['candidate']):
    for file in files:
        if file.endswith(".zip"):
        	dirs_with_zipfiles.append(root)

dirs_with_zipfiles = np.unique(dirs_with_zipfiles) # avoid redundancy
for dir_with_zipfiles in dirs_with_zipfiles:
	unzip_command = "cd "+ dir_with_zipfiles +" && unzip '*.zip' && rm *.zip"	
	os.system(unzip_command)


new_data_dir = os.path.join(paths['candidate'], 'childes.talkbank.org/data-xml')

print('After migrating (`python manage.py makemigrations`; `python manage.py migrate`), you are ready to run `python migrate.py populate_db` from djangoapp, after updating DATA_XML_PATH in config.JSON to point to '+new_data_dir)	
	
	
	



	