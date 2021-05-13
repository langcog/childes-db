#!/usr/bin/env python
import re
import os
import logging
import warnings
import traceback
#from joblib import Parallel, delayed
import multiprocessing
import glob

from multiprocessing_logging import install_mp_handler
from django import db
from django.db.models import Avg, Count, Sum
import db.models
from django.db import transaction

from db.lexical_diversity import mtld, hdd
from db.childes import CHILDESCorpusReader
from db.childes import get_phonology

import functools
import numpy as np
import sys
import time
import fnmatch
import random

import django.db.backends.utils
from django.db import OperationalError
original = django.db.backends.utils.CursorWrapper.execute

#monkey-patch execute_wrapper to try repeatedly until a deadlock has cleared
def execute_wrapper(*args, **kwargs):
    attempts = 0
    attempt_limit = 50
    while attempts < attempt_limit:
        try:
            return original(*args, **kwargs)            
        except OperationalError as e:
            logging.warning('Deadlock... retry #'+str(attempts))            
            code = e.args[0]
            if attempts == (attempt_limit - 1) or code != 1213:
                logging.warning('!!!! Deadlock retries exhausted !!!!!')
                raise e
            attempts += 1
            time.sleep(attempts*.5) #linear backoff

django.db.backends.utils.CursorWrapper.execute = execute_wrapper


def populate_db(collection_root, data_source, selected_collection=None, parallelize=True):    

    populate_db_start_time = time.time()
    logging.basicConfig(level = logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("/home/snair/childes-db/childes_db.log"),
        logging.StreamHandler()
    ])
    logging.info("Populating database")
    results = []
    try:
        if parallelize:
            install_mp_handler()
            manager = multiprocessing.Manager()
            pid_dict = manager.dict()
            pool = multiprocessing.Pool()
        else:
            pool = None

        for collection_name in next(os.walk(collection_root))[1]:       
            if selected_collection and collection_name != selected_collection:
                    continue # skip it if it isn't the selected collection        
            results.append(process_collection(collection_root, collection_name, data_source, pool, pid_dict, parallelize))

        if parallelize:
            pool.close()
            pool.join()

            logging.info('Results:') # this is where error messages should be caught    
            flat_results = flatten_list(results)
            for i in range(len(flat_results)):
                logging.info("Transcript ID " + str(i))
                logging.info(flat_results[i].get())
    except:
        logging.exception("Error in data processing")
        
    
    logging.info('Finished processing all corpora in '+str(round((time.time() - populate_db_start_time) / 60., 3))+' minutes')


def list_directory(directory, type):
    if type == 'folders':
        return(os.walk(directory).__next__()[1])
    if type == 'files':
        return(os.walk(directory).__next__()[2])

def process_collection(collection_root, collection_name, data_source, pool, pid_dict, parallelize):
    
    from db.models import Collection

    logging.info('Processing collection '+collection_name+' at '+os.path.join(collection_root, collection_name))    
    t0 = time.time()
    collection = Collection.objects.create(name=collection_name, data_source = data_source)

    # presence of the zipfiles is what is used to determine what are top-level corpora
    # should find all zipfile_placeholder markers, find corresponding unzipped directories, and treat those as corpora
    
    corpora_to_process = []
    for root, dirnames, filenames in os.walk(os.path.join(collection_root, collection_name)):
        for filename in fnmatch.filter(filenames, '*.zip_placeholder'):
            corpora_to_process.append(os.path.join(root, filename.replace('.zip_placeholder','')))    
    logging.info('Corpus contains '+str(len(corpora_to_process)) +' sub corpora')

    results = []
    for corpus_path in corpora_to_process:
        results.append(process_corpus(corpus_path, os.path.basename(os.path.normpath(corpus_path)), collection_name, data_source, pool, pid_dict, parallelize))

    logging.info('Finished collection '+collection_name +' in '+str(round(time.time() - t0, 3))+' seconds')
    return(flatten_list(results))

        
def process_corpus(corpus_root, corpus_name, collection_name, data_source,  pool, pid_dict, parallelize):

    from db.models import Collection, Corpus    

    collection = Collection.objects.get(name = collection_name, data_source = data_source)

    logging.info('Processing corpus '+corpus_name+' at '+corpus_root)

    processed_file_results = []

    #enumerate all XML files in the corpus directory
    dirs_with_xml = []
    for root, dirs, files in os.walk(corpus_root):
        for file in files:
            if file.endswith(".xml"):
                dirs_with_xml.append(root)
    dirs_with_xml = np.unique(dirs_with_xml)

    logging.info('('+corpus_name+') Number of sub-directories in corpus: '+str(len(dirs_with_xml)))
    
    # Create the corpus object
    corpus = Corpus.objects.create(name=corpus_name, collection=collection, collection_name=collection.name, data_source = data_source)    

    if parallelize:
        
        from django import db
        db.connections.close_all() #make sure all connections are closed before file processing

    for dir_with_xml in dirs_with_xml:

        logging.info('('+corpus_name+') Processing XML directory: '+dir_with_xml)
        nltk_corpus = CHILDESCorpusReader(dir_with_xml, '.*.xml')                        
        for fileid in nltk_corpus.fileids(): # Iterate over all transcripts in this corpus               

            if parallelize:
                processed_file_results.append(pool.apply_async(process_file, args = (fileid, dir_with_xml, corpus, collection, nltk_corpus, pid_dict)))

            else: 
                processed_file_results.append(process_file(fileid, dir_with_xml, corpus, collection, nltk_corpus, None))

        logging.info('('+corpus_name+') Finished directory '+dir_with_xml)    
    
    return(processed_file_results)
    logging.info('Finished corpus!')   


def process_file(fileid, dir_with_xml, corpus, collection, nltk_corpus, pid_dict):

    import django
    django.db.connections.close_all() # make sure that there are no connnections to re-use
    # Models need to be imported again because they are un-pickleable    
    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker


    metadata = nltk_corpus.corpus(fileid)[0]
    
    pid = metadata.get('PID')    
    
    if pid_dict is not None:
        # operating in a  parallel context
        if pid in pid_dict:
            print('File alreadt processed')
            return None
        else:
            pid_dict[pid] = True 

    else:
        # opearting in a serial context
        if Transcript.objects.filter(pid=pid):
            # PID already processed in another file
            return None

    # Create transcript and participant objects up front
    transcript, participants, target_child = create_transcript_and_participants(dir_with_xml, nltk_corpus, fileid, corpus, collection, Transcript, Participant)
    
    process_utterance_results = process_utterances(nltk_corpus, fileid, transcript, participants, target_child, Utterance, Token, TranscriptBySpeaker, TokenFrequency)
    django.db.connections.close_all() # make sure that there are no connnections to re-use
    
    return(process_utterance_results)


def flatten_list(hierarchical_list, list_name = None):    
    # list_name is for debugging
    if list_name is not None:
        logging.info('Flattening '+list_name+' ('+str(len(list_name))+' objects)...')
        logging.info('Example record:')
        logging.info(hierarchical_list)

    return([item for sublist in hierarchical_list for item in sublist if item is not None])

def create_transcript_and_participants(dir_with_xml, nltk_corpus, fileid, corpus, collection, Transcript, Participant):

    # Create transcript object
    metadata = nltk_corpus.corpus(fileid)[0]
    pid = metadata.get('PID')    

    path_components = os.path.normpath(os.path.join(dir_with_xml, fileid)).split(os.sep)
    short_path = '/'.join(path_components[path_components.index(corpus.name)-1::])

    transcript = Transcript.objects.create(
        filename=short_path,
        corpus=corpus,
        corpus_name=corpus.name,
        language=metadata.get('Lang'),
        date=metadata.get('Date'),
        collection=collection,
        collection_name=collection.name,
        pid=pid
    )

    result_participants = []

    # Get all NLTK participants
    nltk_participants = nltk_corpus.participants(fileid)[0]

    # Extract target child from NLTK participants if there is one
    target_child = None
    nltk_target_child, nltk_participants = extract_target_child(nltk_participants)

    # Save target child object
    if nltk_target_child:
        # Get or create django participant object for target child
        target_child = get_or_create_participant(corpus, nltk_target_child, Participant)

        # This participant is its own target child
        target_child.target_child = target_child

        # Mark in transcript as well
        transcript.target_child = target_child
        transcript.target_child_name = target_child.name
        transcript.target_child_age = target_child.age
        transcript.target_child_sex = target_child.sex

        target_child.save()
        transcript.save()

        result_participants.append(target_child)

    # Save all other participants
    for nltk_participant in nltk_participants.values():
        participant = get_or_create_participant(corpus, nltk_participant, Participant, target_child) 
        result_participants.append(participant)

    result_participants = [x for x in result_participants if x is not None]

    return transcript, result_participants, target_child

def bulk_write(token_store, transcript, Token):
    t1 = time.time()        
    with transaction.atomic():
        Token.objects.bulk_create(token_store, batch_size=1000)
    logging.info("("+transcript.filename+") Token, utterance bulk calls completed in "+str(round(time.time() - t1, 3))+' seconds')

def process_utterances(nltk_corpus, fileid, transcript, participants, target_child, Utterance, Token, TranscriptBySpeaker, TokenFrequency):
    
    all_utterance_token_store = []
    token_store = []
    sents = nltk_corpus.get_custom_sents(fileid)    

    for sent in sents:

        # TODO use map instead of tuple
        uID = int(sent[0].replace("u", "")) + 1
        speaker_code = sent[1]
        terminator = sent[2]
        # annotations = sent[3]
        media = sent[4]
        tokens = sent[5]
        actual_pho = sent[6]
        model_pho = sent[7]


        # TODO use map code: participant object
        for participant in participants:
            if participant.code == speaker_code:
                speaker = participant

        if not speaker:
            raise Exception('code not found in participant array: %s, transcript id %s' % (str(speaker_code), str(transcript.pk)))

        if terminator == "p":
            utterance_type = "declarative"
        elif terminator == "q":
            utterance_type = "question"
        elif terminator == "e":
            utterance_type = "imperative_emphatic"
        else:
            utterance_type = terminator

        media_start = float(media['start']) if media else None
        media_end = float(media['end']) if media else None
        media_unit = media['unit'] if media else None        
        
        with transaction.atomic():
            utterance = Utterance.objects.create(
                speaker=speaker,
                transcript=transcript,
                utterance_order=uID,
                type=utterance_type,
                corpus=transcript.corpus,
                corpus_name=transcript.corpus.name,
                actual_phonology = ' '.join(actual_pho),
                model_phonology = ' '.join(model_pho),
                speaker_code=speaker.code,
                speaker_name=speaker.name,
                speaker_role=speaker.role,
                target_child=target_child,
                target_child_name=target_child.name if target_child else None,
                target_child_age=target_child.age if target_child else None,
                target_child_sex=target_child.sex if target_child else None,
                media_start = media_start, # TODO use .get for map
                media_end = media_end,
                media_unit = media_unit,
                collection=transcript.collection,
                collection_name=transcript.collection.name,
                language=transcript.language
            )
        

        utt_gloss = []
        utt_stem = []
        utt_relation = []
        utt_pos = []
        utt_num_morphemes = None

        # TODO nltk token instead of token  
        this_utterance_token_store = []
        for token in tokens:
            # TODO use null or blank?
            gloss = token.get('gloss', '')
            replacement = token.get('replacement', '')
            stem = token.get('stem', '')
            part_of_speech = token.get('pos', '')
            relation = token.get('relation', '')
            token_order = token.get('order', '')
            prefix = token.get('prefix', '')
            suffix = token.get('suffix', '')
            english = token.get('english', '')
            clitic = token.get('clitic', '')
            num_morphemes = token.get('morpheme_length')
            pho = token.get('pho', '')
            mod = token.get('mod', '')

            if gloss:
                utt_gloss.append(gloss)

            if stem:
                utt_stem.append(stem)

            if relation:
                utt_relation.append(relation)

            if num_morphemes:
                if utt_num_morphemes:
                    utt_num_morphemes += num_morphemes
                else:
                    utt_num_morphemes = num_morphemes

            if part_of_speech:
                utt_pos.append(part_of_speech)

            token_record = Token(
                gloss=gloss,
                replacement=replacement,
                prefix=prefix,
                suffix=suffix,
                english=english,
                clitic=clitic,
                stem=stem,
                actual_phonology=pho,
                model_phonology=mod,
                part_of_speech=part_of_speech,
                utterance_type=utterance_type,
                num_morphemes = num_morphemes,
                #relation=relation,                
                #head = None,
                #relation_to_head = None, # relation to dependency requires one to many relationship
                token_order=token_order,
                speaker=speaker,
                utterance=utterance, # what can we do here
                transcript=transcript,
                corpus=transcript.corpus,
                corpus_name=transcript.corpus.name,
                speaker_code=speaker.code,
                speaker_name=speaker.name,
                speaker_role=speaker.role,
                target_child=target_child,
                target_child_name=target_child.name if target_child else None,
                target_child_age=target_child.age if target_child else None,
                target_child_sex=target_child.sex if target_child else None,
                collection=transcript.collection,
                collection_name=transcript.collection.name,
                language=transcript.language
            )
            this_utterance_token_store.append(token_record)


        # # collect all grammatical dependency relations
        # for i in range(len(tokens)):
        #     if this_utterance_token_store[i].relation:
        #         index, head, label = this_utterance_token_store[i].relation.split('|')
        #         this_utterance_token_store[i].head = this_utterance_token_store[int(head)-1]
        #         this_utterance_token_store[i].relation_to_head = label

        all_utterance_token_store.append(this_utterance_token_store)

        # the following are built by iterating through each utterance
        utterance.gloss = ' '.join(utt_gloss)
        utterance.stem = ' '.join(utt_stem)
        #utterance.relation = ' '.join(utt_relation)
        utterance.part_of_speech = ' '.join(utt_pos)
        utterance.num_morphemes = utt_num_morphemes
        utterance.num_tokens = len(utt_gloss)                
        with transaction.atomic():
            utterance.save()

    token_store = flatten_list(all_utterance_token_store)

    bulk_write(token_store, transcript, Token)

    TranscriptBySpeaker_store = []
    TokenFrequency_store = []
    
    for participant in participants:
        speaker_utterances = Utterance.objects.filter(speaker=participant, transcript=transcript)
        speaker_tokens = Token.objects.filter(speaker=participant, transcript=transcript)

        num_utterances = speaker_utterances.count()
        mlu_w = speaker_utterances.aggregate(Avg('num_tokens'))['num_tokens__avg']
        num_types = speaker_tokens.values('gloss').distinct().count()
        num_tokens = speaker_tokens.values('gloss').count()
        num_morphemes = speaker_utterances.aggregate(Sum('num_morphemes'))['num_morphemes__sum']
        mlu_m = speaker_utterances.aggregate(Avg('num_morphemes'))['num_morphemes__avg']

        tbs = TranscriptBySpeaker(
            transcript=transcript,
            corpus=transcript.corpus,
            speaker=participant,
            speaker_role=participant.role,
            target_child=target_child,
            target_child_name=target_child.name if target_child else None,
            target_child_age=target_child.age if target_child else None,
            target_child_sex=target_child.sex if target_child else None,
            num_utterances=num_utterances,
            mlu_w=mlu_w,
            mlu_m=mlu_m,
            mtld=mtld(speaker_tokens),
            hdd=hdd(speaker_tokens),
            num_types=num_types,
            num_tokens=num_tokens,
            num_morphemes=num_morphemes,
            collection=transcript.collection,
            collection_name=transcript.collection.name,
            language = transcript.language
        )
        TranscriptBySpeaker_store.append(tbs)

        gloss_counts = speaker_tokens.values('gloss').annotate(count=Count('gloss'))
        for gloss_count in gloss_counts:
            tf = TokenFrequency(
                transcript=transcript,
                corpus=transcript.corpus,
                gloss=gloss_count['gloss'],
                count=gloss_count['count'],
                speaker=participant,
                speaker_role=participant.role,
                target_child=target_child,
                target_child_name=target_child.name if target_child else None,
                target_child_age=target_child.age if target_child else None,
                target_child_sex=target_child.sex if target_child else None,
                collection=transcript.collection,
                collection_name=transcript.collection.name,
                language=transcript.language
            )
            TokenFrequency_store.append(tf)

    t2 = time.time()
    with transaction.atomic():
        TranscriptBySpeaker.objects.bulk_create(TranscriptBySpeaker_store, batch_size=1000) 
    with transaction.atomic():
        TokenFrequency.objects.bulk_create(TokenFrequency_store, batch_size=1000) 
    logging.info("("+transcript.filename+") TranscriptBySpeaker, TokenFrequency bulk calls completed in "+str(round(time.time() - t2, 3))+' seconds')

    return('success')
    
def extract_target_child(participants):
    nltk_target_child = None
    code_to_pop = None

    for code, nltk_participant in participants.items():
        # TODO use code = CHI as well
        if nltk_participant.get('role') == 'Target_Child':
            if nltk_target_child:
                # 2 target children in this transcript, return None
                return None, participants
            else:
                nltk_target_child = nltk_participant
                code_to_pop = code

    if code_to_pop:
        participants.pop(code_to_pop)
    return nltk_target_child, participants


def parse_age(age):
    age_in_days = 0

    # parse ISO 8601 time interval
    for number, unit in re.findall('(?P<number>\d+)(?P<period>M|D|Y)', (age or '').split('T')[0]):
        number = int(number)
        if unit == 'Y':
            age_in_days += number * 365.25
        elif unit == 'M':
            age_in_days += number * 365.25 / 12
        elif unit == 'D':
            age_in_days += number

    return age_in_days if age_in_days != 0 else None


def update_age(participant, age):
    if age:
        if not participant.min_age:
            participant.min_age = age

        if participant.min_age and age < participant.min_age:
            participant.min_age = age

        if not participant.max_age:
            participant.max_age = age

        if participant.max_age and age > participant.max_age:
            participant.max_age = age


def get_or_create_participant(corpus, attr_map, Participant, target_child=None):

    if not attr_map:
        print('attr_map is None in get_or_create_participant')
        return None

    age = parse_age(attr_map.get('age'))
    code = attr_map.get('id')
    name = attr_map.get('name')
    role = attr_map.get('role')
    language = attr_map.get('language')
    group = attr_map.get('group')
    sex = attr_map.get('sex')
    ses = attr_map.get('SES')
    education = attr_map.get('education')
    custom = attr_map.get('custom')

    # this is searching for the set of participants -- this disallows regenerating it
    with transaction.atomic():
        query_set = Participant.objects.select_for_update().filter(code=code, name=name, role=role, corpus=corpus)
        # this code should lock the participant to help avoid deadlocks

        # Filter participant candidates by target child
        if target_child:
            query_set = query_set.filter(target_child=target_child)

        participant = query_set.first()
        
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
                corpus=corpus,
                corpus_name=corpus.name,
                collection=corpus.collection,
                collection_name=corpus.collection.name
            )
            if target_child:
                participant.target_child = target_child

        update_age(participant, age)

        # TODO very confusing. in memory attribute gets passed to child process
        # Mark the age for this participant for this transcript, to be saved in utterance / token as speaker_age
        participant.age = age

        participant.save()

    return participant
