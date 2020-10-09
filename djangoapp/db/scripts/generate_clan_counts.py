import os
import re
import json
import logging
import multiprocessing
from pathlib import Path

# TODO put in settings file
CHA_DIR = '/shared_hd1/childes-db-cha/'
PATTERN = 'Total number of different item types used\n(.*)Total number of items'
SPEAKER_PATTERN = 'Speaker:(.*):'
CLAN_CMD = "~/utils/unix-clan/unix/bin/freq "
BY_SPEAKER = True

multiprocessing.log_to_stderr()
logger = multiprocessing.get_logger()
logger.setLevel(logging.INFO)


def clan_unigram_count(path):
    output = os.popen(CLAN_CMD + path).read()
    subtotals = re.findall(PATTERN, output)
    return sum(map(int, subtotals))

def clan_unigram_count_by_speaker(path):
    output = os.popen(CLAN_CMD + path).read()
    speakers = re.findall(SPEAKER_PATTERN, output)
    counts = re.findall(PATTERN, output)
    assert len(speakers) == len(counts)
    speaker_dict = {}
    for i, elem in enumerate(speakers):
        speaker_dict[elem.strip().replace('*','')] = int(counts[i])
    return speaker_dict


def write_to_file(corpus_results):
    clan_counts = {}

    if BY_SPEAKER:
        filename = 'clan_counts_by_speaker.json'
        for corpus_dir, result_arr in corpus_results.iteritems():
            speaker_dict_arr = [r.get() for r in result_arr]
            for speaker_dict in speaker_dict_arr:
                for speaker, speaker_count in speaker_dict.iteritems():
                    key = corpus_dir + '_' + speaker
                    clan_counts[key] = clan_counts.get(key, 0) + speaker_count
    else:
        filename = 'clan_counts.json'
        for corpus_dir, result_arr in corpus_results.iteritems():
            clan_counts[corpus_dir] = sum([r.get() for r in result_arr])

    print clan_counts
    with open(filename, 'w') as outfile:
        json.dump(clan_counts, outfile)


if __name__ == '__main__':
    pool = multiprocessing.Pool()
    corpus_results = {}

    func = clan_unigram_count_by_speaker if BY_SPEAKER else clan_unigram_count
    for collection_dir in os.listdir(CHA_DIR):
        for corpus_dir in os.listdir(os.path.join(CHA_DIR, collection_dir)):
            corpus_results[corpus_dir] = []
            path_list = Path(os.path.join(CHA_DIR, collection_dir, corpus_dir)).glob('**/*.cha')

            for path in path_list:
                corpus_results[corpus_dir].append(pool.apply_async(func, args=(str(path),)))

    pool.close()
    write_to_file(corpus_results)



