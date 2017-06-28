from models import Collection, Transcript, Participant, Utterance, Token, Corpus
import multiprocessing
import re
import logging
import os
import traceback
from django import db

def migrate():
    from childes import CHILDESCorpusReader

    multiprocessing.log_to_stderr()
    logger = multiprocessing.get_logger()
    logger.setLevel(logging.INFO)

    pool = multiprocessing.Pool()
    results = []

    root = '/home/alsan/corpora/childes-xml/'
    # test_total = 0
    for collection_name in os.listdir(root):

        if collection_name == 'Spanish':
            continue

        corpus_root = root + collection_name
        collection_obj = Collection.objects.create(name=collection_name)

        for corpus_name in os.listdir(corpus_root):
            # test_total += 1
            # if test_total > 3:
            #     pool.close()
            #     for result in results:
            #         try:
            #             result.get()
            #         except:
            #             traceback.print_exc()
            #     return 'done'
            print corpus_name
            nltk_corpus = CHILDESCorpusReader(corpus_root, corpus_name + '/.*.xml')
            django_corpus = Corpus.objects.create(name=corpus_name, collection=collection_obj)

            # necessary so child process doesn't inherit file descriptor
            db.connections.close_all()

            for fileid in nltk_corpus.fileids():
                results.append(pool.apply_async(process_transcript, args=(nltk_corpus, django_corpus.pk, fileid)))

    pool.close()

    # catch any exceptions thrown by child processes
    for result in results:
        try:
            result.get()
        except:
            traceback.print_exc()

def process_transcript(corpus, corpus_pk, fileid):
    corpus_obj = Corpus.objects.get(pk=corpus_pk)

    # transcript info
    t = Transcript(filename=fileid, corpus=corpus_obj)
    corpus_data = corpus.corpus(fileid)
    for key, val in corpus_data[0].iteritems():
        if key == 'Lang':
            t.languages = val
        elif key == 'Date':
            t.date = val
        elif key == 'Comment':
            t.comment = val
    t.save()


    # participant info
    participants = corpus.participants(fileid)[0]

    participants_in_this_transcript = []

    for key, val in participants.iteritems():

        code = key

        # part = Participant(code=key, corpus=corpus_obj, transcript=t)
        name = val.get('name')
        role = val.get('role')

        age_in_days = 0

        # parse ISO 8601 time interval
        for number, unit in re.findall('(?P<number>\d+)(?P<period>M|D|Y)', val.get('age', '').split('T')[0]):
            number = int(number)
            if unit == 'Y':
                age_in_days += number * 365.25
            elif unit == 'M':
                age_in_days += number * 30
            elif unit == 'D':
                age_in_days += number

        age = age_in_days if age_in_days != 0 else None
        language = val.get('language')
        group = val.get('group')
        sex = val.get('sex')
        ses = val.get('SES')
        education = val.get('education')
        custom = val.get('custom')

        participant = Participant.objects.filter(code=code, name=name, role=role, corpus=corpus_obj).first()
        if not participant:
            participant = Participant.objects.create(
                code=code,
                name=name,
                role=role,
                language=language,
                group=group,
                sex=sex,
                ses=ses,
                education=education,
                custom=custom,
                corpus=corpus_obj
            )
        participant.age = age # this shouldn't get saved, but needs to get used later on...


        # update min / max age, need to refactor
        if age and not participant.min_age:
            participant.min_age = age

        if age and participant.min_age and age < participant.min_age:
            participant.min_age = age

        if age and not participant.max_age:
            participant.max_age = age

        if age and participant.max_age and age > participant.max_age:
            participant.max_age = age

        participant.save()

        participants_in_this_transcript.append(participant)


    # get 1 target child, if possible
    num_target_children = 0
    target_child = None
    for participant in participants_in_this_transcript:
        if participant.role == 'Target_Child': # if none, and there is one CHI use that one
            num_target_children += 1
            target_child = participant

    # set transcript and all participant target child to one found above
    if num_target_children == 1:
        t.target_child = target_child
        t.target_child_age = target_child.age # attribute added above
        t.save()
        for part in participants_in_this_transcript:
            part.target_child = target_child
            part.save()

    # utterance and token

    sents = corpus.get_custom_sents(fileid)
    for sent in sents:
        uID = int(sent[0].replace("u", "")) + 1
        speaker = sent[1]
        tokens = sent[2]

        # speaker_obj = Participant.objects.get(transcript=t, code=speaker)
        # speaker_obj = Participant.objects.get(corpus=corpus_obj, )
        for participant in participants_in_this_transcript:
            if participant.code == speaker:
                speaker_obj = participant

        if not speaker_obj:
            raise Exception('code not found in participant array: %s, transcript id %s' % (str(speaker), str(t.pk)))

        utt = Utterance(
            speaker=speaker_obj,
            transcript=t,
            order=uID,
            corpus=corpus_obj,
            speaker_code=speaker_obj.code,
            speaker_name=speaker_obj.name,
            speaker_age=speaker_obj.age,
            speaker_role=speaker_obj.role
        )
        utt.save()

        utt_gloss = []
        utt_stem = []
        utt_relation = []
        utt_pos = []

        for token in tokens:
            gloss = token.get('gloss', '')
            replacement = token.get('replacement', '')
            stem = token.get('stem', '')
            part_of_speech = token.get('pos', '')
            relation = token.get('relation', '')
            token_order = token.get('order', '')

            if gloss:
                utt_gloss.append(gloss)

            if stem:
                utt_stem.append(stem)

            if relation:
                utt_relation.append(relation)

            if part_of_speech:
                utt_pos.append(part_of_speech)

            tok = Token(
                gloss=gloss,
                replacement=replacement,
                stem=stem,
                part_of_speech=part_of_speech,
                relation=relation,
                token_order=token_order,
                speaker=speaker_obj,
                utterance=utt,
                transcript=t,
                corpus=corpus_obj,
                speaker_code=speaker_obj.code,
                speaker_name=speaker_obj.name,
                speaker_age=speaker_obj.age,
                speaker_role=speaker_obj.role
            )
            tok.save()

        utt.gloss = ' '.join(utt_gloss)
        utt.stem = ' '.join(utt_stem)
        utt.relation = ' '.join(utt_relation)
        utt.part_of_speech = ' '.join(utt_pos)
        utt.length = len(utt_gloss)
        utt.save()





