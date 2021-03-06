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


"""


MLU


"""

CHA_DIR = '/home/alsan/all_cha/childes.talkbank.org/data/'
#PATTERN = 'Total number of different item types used\n(.*)Total number of items'
PATTERN = 'Ratio of words over utterances =(.*)\n'
SPEAKER_PATTERN = 'Speaker:(.*):'


def clan_mlu_count_by_speaker(path): # main function
    #print path
    output = os.popen('~/legacy/CLAN/unix-clan/unix/bin/mlu -t%mor ' + path + ' 2> /dev/null').read()
    speakers = re.findall(SPEAKER_PATTERN, output)
    counts = re.findall(PATTERN, output)

    if len(speakers) != len(counts):
        return {}

    #assert len(speakers) == len(counts)
    speaker_dict = {}
    for i, elem in enumerate(speakers):
        speaker_dict[elem.strip().replace('*', '')] = float(counts[i])
    return speaker_dict

def get_mlu(path, corpus_root):
    filename = str(path).split(corpus_root)[1].replace("cha", "xml")
    #print filename
    tr = Transcript.objects.filter(filename=filename)

    if not tr:
        return None, None

    m = clan_mlu_count_by_speaker(str(path))

    if not m: return None, None

    l1, l2 = [], []

    for code, count in m.iteritems():
        row = TranscriptBySpeaker.objects.filter(transcript=tr, speaker__code=code)
        if row and count and row[0].mlu:
            l1.append(count)
            l2.append(row[0].mlu)
        else:
            print "oops not found ", tr.id, code
            return None, None
    #print l1, l2
    return l1,l2


def count_corpora(corpus_root):
    total_collection_l1, total_collection_l2 = [], []

    for corpus_dir in os.walk(corpus_root).next()[1]:
        # if corpus_dir != "Clark":
        #    continue

        print "||| ", corpus_dir
        # corpus_results[corpus_dir] = []
        path_list = Path(os.path.join(corpus_root, corpus_dir)).glob('**/*.cha')

        for path in path_list:
            l1, l2 = get_mlu(path, corpus_root + "/")
            if l1 and l2:
                total_collection_l1.extend(l1)
                total_collection_l2.extend(l2)

    return total_collection_l1, total_collection_l2

#The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "test mlu counts"

    # A command must define handle()
    def handle(self, *args, **options):
        multiprocessing.log_to_stderr()
        logger = multiprocessing.get_logger()
        logger.setLevel(logging.INFO)

        pool = multiprocessing.Pool()
        corpus_results = {}

        results = []

        total_l1 = []
        total_l2 = []

        for collection_name in os.walk(CHA_DIR).next()[1]:

            # test?
            #if collection_name != "Eng-NA": continue
            print "*** ", collection_name

            corpus_root = os.path.join(CHA_DIR, collection_name)
            #print corpus_root

            if os.walk(corpus_root).next()[2]:
                # corpora in here (i.e. *.zip files present)
                #results += crawl_corpora(corpus_root, collection, pool)

                results.append(pool.apply_async(count_corpora, args=(corpus_root,)))

                #t1, t2 = count_corpora(corpus_root) # add pool
                #total_l1.extend(t1)
                #total_l2.extend(t2)
            else:
                # go past subdirectories (i.e. Korea, Indonesian, etc.)
                for dir in os.walk(corpus_root).next()[1]:
                    #results += crawl_corpora(corpus_root + "/" + dir, collection, pool)
                    # t1, t2 = count_corpora(corpus_root + "/" + dir)  # add pool
                    # total_l1.extend(t1)
                    # total_l2.extend(t2)

                    results.append(pool.apply_async(count_corpora, args=(corpus_root + "/" + dir,)))

        pool.close()

        for result in results:
            try:
                t1, t2 = result.get()
                total_l1.extend(t1)
                total_l2.extend(t2) # would need a map for special subsetting
            except:
                traceback.print_exc()

        a = numpy.asarray([total_l1, total_l2])
        numpy.savetxt("mlu.csv", a.transpose(), delimiter=",", fmt='%.3e')

        coeff = numpy.corrcoef(total_l1, total_l2)[0, 1]
        print coeff
        os.system("echo %s > mlu_coeff.txt" % coeff)



                #corpus_results[corpus_dir].append(pool.apply_async(func, args=(str(path),)))

        #pool.close()
        #write_to_file(corpus_results)

