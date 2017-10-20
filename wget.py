import numpy as np

def parse_wget_output(log_path):
	'''check if any of the requests returned a 200 (success) indicating that it's time to reprocess the database'''

	with open(log_path, 'r') as content_file:
		content = content_file.read()

	lines = np.array(content.split('\n'))    	

	changed_indices = np.array([line.startswith('Saving to:') for line in lines])	

	index_indices = np.array([(line.find('index.html') != -1) for line in lines])

	return(list(lines[np.where(changed_indices & ~index_indices)]))