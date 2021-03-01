import os
import numpy
import traceback
import multiprocessing
import logging
from pathlib import Path
import re
from django.conf import settings
from django.core.management import BaseCommand
from db.models import Transcript, TranscriptBySpeaker
import fnmatch
from pathlib import Path


COLLECTION_ROOTS = ['/shared_hd2/childes-db/2020.1/candidate/phonbank.talkbank.org/data', '/shared_hd2/childes-db/2020.1/candidate/childes.talkbank.org/data']
PATTERN = 'Total number of different item types used\n(.*)Total number of items'
SPEAKER_PATTERN = 'Speaker:(.*):'
CLAN_CMD = "~/utils/unix-clan/unix/bin/freq "
PARALLEL= True

# iterate over /shared_hd0/corpora/childes_new
# run freq
# using name of transcript, fetch numbers from transcript by speaker table
# compute correlation between counts

def clan_unigram_count_by_speaker(path):
    output = os.popen(CLAN_CMD + path + ' 2> /dev/null').read()
    speakers = re.findall(SPEAKER_PATTERN, output)
    counts = re.findall(PATTERN, output)
    assert len(speakers) == len(counts)
    speaker_dict = {}
    for i, elem in enumerate(speakers):
        speaker_dict[elem.strip().replace('*', '')] = int(counts[i])
    return speaker_dict

def get_counts(path, corpus_root):    
    

    corpus_name =  corpus_root.split('/')[-1]
    throwaway, path_in_db = path.split(corpus_name+'/')
    path_in_db = os.path.join(corpus_name, path_in_db.replace(".cha",".xml"))
     # corpus_name should return the segment of the path between /data/ and the location of the zip_placeholder, e.g. "Scandanabian/Norwegian"
    
    # if not 'Scandanavian' in path.split('/'):
    #     return None, None, None
    # corpus name and lower should be findable in the database with like %x%

    #data_prefix = /shared_hd2/childes-db/2020.1/candidate/phonbank.talkbank.org/data/
    #corpus_name ={Dutch, Scandanavian}
    
    tr = Transcript.objects.filter(filename__contains=path_in_db)

    if not tr:
        print('Transcript not found in database: '+path_in_db)
        return None, None, None, path
    if len(tr) > 1:
        print('Multiple records found for corpus name '+path_in_db)
        return None, None, None, path

    m = clan_unigram_count_by_speaker(path)

    l1, l2, missing = [], [], []

    for code, count in m.items():
        row = TranscriptBySpeaker.objects.filter(transcript=tr, speaker__code=code)
        if row:
            l1.append(count)
            l2.append(row[0].num_tokens)
        else:
            print("Transcript + Code combination not found! ", path_in_db, code)
            missing.append((path_in_db, code)) 
            return None, None, missing, path
    return(l1,l2, missing, path)


def count_corpora(corpus_root):
    corpus_collection_l1, corpus_collection_l2, corpus_missing, corpus_filenames  = [], [], [], []

    for subcorpus_dir in os.walk(corpus_root).__next__()[1]:
        #if corpus_dir != "Clark":
         #   continue

        print("||| ", subcorpus_dir)
        # corpus_results[corpus_dir] = []
        path_list = Path(os.path.join(corpus_root, subcorpus_dir)).glob('**/*.cha')
        
        for path in set(path_list):
            l1, l2, missing, filename = get_counts(str(path), corpus_root)
            if l1 and l2:
                corpus_collection_l1.extend(l1)
                corpus_collection_l2.extend(l2)
                corpus_missing.extend(missing)
                corpus_filenames.extend(filename)

    return corpus_collection_l1, corpus_collection_l2, corpus_missing, corpus_filenames

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "test frequency counts"

    # A command must define handle()
    def handle(self, *args, **options):
        multiprocessing.log_to_stderr()
        logger = multiprocessing.get_logger()
        logger.setLevel(logging.INFO)

        if PARALLEL:
            pool = multiprocessing.Pool()
        
        corpus_results = {}
        results = []
        total_l1 = []
        total_l2 = []
        filenames = []
        
        for collection_root in COLLECTION_ROOTS: #iterate over phonbank and CHILDES
            for collection_name in next(os.walk(collection_root))[1]:       
                
                print("*** ", collection_name)
                corpus_roots = []
                
                for root, dirnames, filenames in os.walk(os.path.join(collection_root, collection_name)):
                    for filename in fnmatch.filter(filenames, '*.zip_placeholder'):
                        corpus_roots.append(os.path.join(collection_root, collection_name, root, filename.replace('.zip_placeholder','')))

                corpus_roots = list(set(corpus_roots))
                print('Corpora to process: '+str(len(corpus_roots)))

                for corpus_root in corpus_roots:
                    if PARALLEL:
                        results.append(pool.apply_async(count_corpora, args=(corpus_root,)))
                    else:
                        results.append(count_corpora(corpus_root,))

        if PARALLEL:
            pool.close()

        for result in results:
            try:
                t1, t2, missing, filename = result.get()
                total_l1.extend(t1)
                total_l2.extend(t2) # would need a map for special subsetting
                filenames.extend(filename)
            except:
                traceback.print_exc()
        
        counts = numpy.asarray([total_l1, total_l2])
        numpy.savetxt("freq.csv", counts.transpose(), delimiter=",", fmt='%.3e')

        print('Number of transcripts in correlation:')
        print(len(total_l1))
        coeff = numpy.corrcoef(total_l1, total_l2)[0, 1]
        print("Correlation coefficient (Pearson's r)")
        print(coeff)
        os.system("echo %s > word_frequency_correlation.txt" % coeff)

        import pdb
        pdb.set_trace()