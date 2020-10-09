import os
import re
import csv
import json
import logging
import StringIO
import multiprocessing
from pathlib import Path
from collections import Counter

# TODO put in settings file
CHA_DIR = '/shared_hd1/childes-db-cha/'
PATTERN = 'Total number of different item types used\n(.*)Total number of items'
CLAN_CMD = "~/utils/unix-clan/unix/bin/freq "
SPEAKER_PATTERN = 'Speaker:(.*):'
BY_SPEAKER = True

IGNORED_FIELDNAMES = [
    'Speaker',
    'File',
    'Language',
    'Corpus',
    'Age',
    'Sex',
    'Group',
    'SES',
    'Role',
    'Education',
    'Custom field',
    'Types',
    'Token',
    'TTR'
]

multiprocessing.log_to_stderr()
logger = multiprocessing.get_logger()
logger.setLevel(logging.INFO)


def clan_unigram_count(path):
    output = os.popen(CLAN_CMD + path).read()
    subtotals = re.findall(PATTERN, output)
    return sum(map(int, subtotals))

# d = {elem['gloss']:elem['total'] for elem in s}
def clan_unigram_count_by_token(path):
    # +r5: don't replace
    # +r6: include repetitions
    # +d2: output in spreadsheet format
    # +o3 combine all speakers
    # -f: print output to tsv
    tsv = os.popen(CLAN_CMD + ' +r5 +r6 +d2 +o3 -f ' + path).read()
    word_freq_dict = {}


    f = StringIO.StringIO(tsv)
    reader = csv.DictReader(f, dialect="excel-tab")
    # header = next(reader)
    #
    # speaker_ind, start_ind, end_ind = 3, None, None
    #
    # generator = (index for index, column in enumerate(header) if column.startswith('*'))
    # for start_ind in generator:
    #     pass
    #
    # end_ind = next(index for index, column in enumerate(header) if column == 'Types')

    print '\n\n\n\n\n\n'

    last_row = None
    total = 0
    for row in reader:
        total += 1
        print total
        print 'printing banana:'
        print row['banana']
        print 'printing File'
        print row['File']
        if not row['File']:
            last_row = row

    print '\n\n\n\n\n'
    #print row
    print len(row)

    # t = 0
    # for k, v in row.iteritems():
    #     t += 1
    #     print t
    #     print 'key: {}'.format(k)
    #     print 'value: {}'.format(v)
    #     k.startswith('p')


    result = {k:v for k, v in row.iteritems() if not (k is None or k.startswith('*') or k in IGNORED_FIELDNAMES)}

    return result # filter by non essentials in header

    # for word, freq in last_row.iteritems():
    #     word_freq_dict[]
    #
    # for row in reader:
    #     word_freq_dict[row[]]
    #
    # speakers = re.findall(SPEAKER_PATTERN, output)
    # counts = re.findall(PATTERN, output)
    # assert len(speakers) == len(counts)
    # speaker_dict = {}
    # for i, elem in enumerate(speakers):
    #     speaker_dict[elem.strip().replace('*','')] = int(counts[i])
    # return speaker_dict


def write_to_file(corpus_results):
    clan_counts = {}

    # if BY_SPEAKER:
    #     filename = 'clan_counts_by_speaker.json'
    #     for corpus_dir, result_arr in corpus_results.iteritems():
    #         speaker_dict_arr = [r.get() for r in result_arr]
    #         for speaker_dict in speaker_dict_arr:
    #             for speaker, speaker_count in speaker_dict.iteritems():
    #                 key = corpus_dir + '_' + speaker
    #                 clan_counts[key] = clan_counts.get(key, 0) + speaker_count
    # else:
    #     filename = 'clan_counts.json'
    #     for corpus_dir, result_arr in corpus_results.iteritems():
    #         clan_counts[corpus_dir] = sum([r.get() for r in result_arr])
    filename = 'clan_token_counts.json'

    for corpus_dir, freq_arr in corpus_results.iteritems():
        final_dict = sum([Counter(r.get()) for r in freq_arr], Counter())
        clan_counts[corpus_dir] = dict(final_dict)

    # print clan_counts
    with open(filename, 'w') as outfile:
        json.dump(clan_counts, outfile)


if __name__ == '__main__':
    pool = multiprocessing.Pool()
    corpus_results = {}
    #  s = Token.objects.filter(transcript_id=4195).values('gloss').annotate(total=Count('pk'))
    # func = clan_unigram_count_by_token if BY_SPEAKER else clan_unigram_count

    total = 0
    for corpus_dir in os.listdir(CHA_DIR):
        total += 1
        if total > 2:
            break
        corpus_results[corpus_dir] = []
        path_list = Path(os.path.join(CHA_DIR, corpus_dir)).glob('**/*.cha')

        for path in path_list:
            corpus_results[corpus_dir].append(pool.apply_async(clan_unigram_count_by_token, args=(str(path),)))

       # if total > 1: break

    pool.close()
    write_to_file(corpus_results)



