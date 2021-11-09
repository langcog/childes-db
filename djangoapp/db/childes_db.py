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
from db.transcripts_participants import create_transcript_and_participants, process_transcript_by_speaker
from db.utils import bulk_write, flatten_list, parse_age, update_age, extract_target_child
from db.lexical_diversity import mtld, hdd

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
        logging.FileHandler("populate_db.log"),
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

def test_single_corpus(collection_root, selected_corpus, data_source, selected_collection):
    
    single_corpus_start_time = time.time()
    results = []

    pool = None
    pid_dict = {}

    results.append(process_collection(collection_root, selected_collection, data_source, pool, pid_dict, parallelize=False, selected_corpora = [selected_corpus]))

    logging.info('Results:') # this is where error messages should be caught    
    flat_results = flatten_list(results)    
    logging.info(flat_results)
 
    logging.info('Finished processing single corpus in '+str(round((time.time() - single_corpus_start_time) / 60., 3))+' minutes')


def list_directory(directory, type):
    if type == 'folders':
        return(os.walk(directory).__next__()[1])
    if type == 'files':
        return(os.walk(directory).__next__()[2])

def process_collection(collection_root, collection_name, data_source, pool, pid_dict, parallelize, selected_corpora = None):
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

    # limit the files to those in the selected corpus
    if selected_corpora is not None:
        include_mask = np.array([np.any([x.find(y) != -1  for y in selected_corpora])  for x in corpora_to_process])
        corpora_to_process =np.array(corpora_to_process)[include_mask]
    
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
            logging.debug('File already processed')
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


def process_utterances(nltk_corpus, fileid, transcript, participants, target_child, Utterance, Token, TranscriptBySpeaker, TokenFrequency):
    all_utterance_token_store = [] # utterance_store
    token_store = []
    sents = nltk_corpus.get_custom_sents(fileid)    

    for sent in sents:

        # TODO use map instead of tuple
        uID = int(sent['sent_id'].replace("u", "")) + 1
        speaker_code = sent['speaker']
        terminator = sent['term']
        annotations = sent['annotations'] #do we use this?
        media = sent['media']
        tokens = sent['tokens']
        actual_pho = sent['actual_pho']
        model_pho = sent['model_pho']
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
        
        all_utterance_token_store = process_utterance_tokens(tokens, utterance, token_store, all_utterance_token_store, utterance_type, speaker, transcript, target_child, Token)
        t1 = time.time()        
        Token.objects.bulk_create(token_store, batch_size=1000)
        logging.info("("+transcript.corpus_name+'/'+transcript.filename+") Token, utterance bulk calls completed in "+str(round(time.time() - t1, 3))+' seconds')


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

def process_utterance_tokens(tokens, utterance, token_store, all_utterance_token_store, utterance_type, speaker, transcript, target_child, Token):
    utt_gloss = []
    utt_stem = []
    utt_relation = []
    utt_pos = []
    utt_num_morphemes = None

    this_utterance_token_store = []
    for token in tokens:
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
    return all_utterance_token_store
