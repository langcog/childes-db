#!/usr/bin/env python
import re
import os
import logging
import warnings
import traceback
#from joblib import Parallel, delayed
import multiprocessing
import glob
import time

from django import db
from django.db.models import Avg, Count, Sum
import db.models


from db.lexical_diversity import mtld, hdd
from db.childes import CHILDESCorpusReader
from db.childes import get_phonology
from db.transcripts_participants import create_transcript_and_participants, process_transcript_by_speaker


import functools
import numpy as np
import sys
import time

def populate_db(collection_root, selected_collection=None, parallelize=False):    

    populate_db_start_time = time.time()
    multiprocessing.log_to_stderr()
    logger = multiprocessing.get_logger()
    logger.setLevel(logging.INFO)

    results = []

    if parallelize:
        pool = multiprocessing.Pool()
    else:
        pool = None

    for collection_name in next(os.walk(collection_root))[1]:       
        if selected_collection and collection_name != selected_collection:
            continue # skip it if it isn't the selected collection        
        results.append(process_collection(collection_root, collection_name, pool, parallelize))

    if parallelize:
        pool.close()
        pool.join()

    print('Finished processing all corpora in '+str(round((time.time() - populate_db_start_time) / 60., 3))+' minutes')

def process_collection(collection_root, collection_name, pool, parallelize):
    
    from db.models import Collection

    print('Processing collection '+collection_name+' at '+os.path.join(collection_root, collection_name))    
    t0 = time.time()
    collection = Collection.objects.create(name=collection_name)

    results = []

    # the top level of a collection is the corpora    
    top_level_corpora_in_collection = [os.path.basename(os.path.normpath(x)) for x in glob.glob(os.path.join(collection_root, collection_name,'*/')) ]       

    print('Corpus contains '+str(len(top_level_corpora_in_collection)))

    # apply_async
    for corpus_name in top_level_corpora_in_collection:
        results.append(process_corpus(os.path.join(collection_root, collection_name), corpus_name, collection_name, pool, parallelize))

    # dumb parallelization
    #results = Parallel(n_jobs=24)(delayed(process_corpus)(os.path.join(collection_root, collection_name), corpus_name, collection_name) for corpus_name in top_level_corpora_in_collection)

    print('Finished collection '+collection_name +' in '+str(round(time.time() - t0, 3))+' seconds')
    return(results)

        
def process_corpus(corpus_root, corpus_name, collection_name, pool, parallelize):

    from db.models import Collection, Corpus

    # retrieve the Collection from within the process so we don't need to pass the Django ORM object, which is unpickleable
    collection = Collection.objects.get(name = collection_name)
    corpus_path = os.path.join(corpus_root, corpus_name)

    print('Processing corpus '+corpus_name+' at '+corpus_path)

    processed_file_results = []

    dirs_with_xml = []
    for root, dirs, files in os.walk(os.path.join(corpus_root, corpus_name)):
        for file in files:
            if file.endswith(".xml"):
                dirs_with_xml.append(root)
    dirs_with_xml = np.unique(dirs_with_xml)

    print('('+corpus_name+') Number of sub-directories in corpus: '+str(len(dirs_with_xml)))
    
    corpus = Corpus.objects.create(name=corpus_name, collection=collection, collection_name=collection.name)
    # here, creating a corpus for every subdirectory -- this is not right
    
    for dir_with_xml in dirs_with_xml:
        print('('+corpus_name+') Processing XML directory: '+dir_with_xml)

        nltk_corpus = CHILDESCorpusReader(dir_with_xml, '.*.xml')        
        
        # Iterate over all transcripts in this corpus        
        
        for fileid in nltk_corpus.fileids():


            if parallelize:
                processed_file_results.append(pool.apply_async(process_file, args = (fileid, dir_with_xml, corpus, collection, nltk_corpus)))

            else: 
                processed_file_results.append(process_file(fileid, dir_with_xml, corpus, collection, nltk_corpus))
        print('('+corpus_name+') Finished directory '+dir_with_xml)

    return(processed_file_results)
    print('Finished corpus!')   


def process_file(fileid, dir_with_xml, corpus, collection, nltk_corpus):

    import django
    django.setup()
    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker
        
    # Create transcript and participant objects up front
    transcript, participants, target_child = create_transcript_and_participants(dir_with_xml, nltk_corpus, fileid, corpus, collection)

    # Ignore old filenames (due to recent update)
    if not transcript:
        return(None)

    # necessary so child process doesn't inherit file descriptor
    #db.connections.close_all()
    
    process_utterance_results = process_utterances(nltk_corpus, fileid, transcript, participants, target_child)

    return(process_utterance_results)

def process_utterances(nltk_corpus, fileid, transcript, participants, target_child):

    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker
    
    utterance_store = []
    token_store = []
    sents = nltk_corpus.get_custom_sents(fileid)    
    
    #utterance_store = {}

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
        
        process_utterance_tokens(tokens, utterance, token_store, utterance_type, speaker, transcript, target_child)
    
    t1 = time.time()        
    Token.objects.bulk_create(token_store, batch_size=1000)
    print("("+transcript.corpus_name+'/'+transcript.filename+") Token, utterance bulk calls completed in "+str(round(time.time() - t1, 3))+' seconds')


    TranscriptBySpeaker_store = []
    TokenFrequency_store = []
    
    for participant in participants:
        speaker_utterances = Utterance.objects.filter(speaker=participant, transcript=transcript)
        speaker_tokens = Token.objects.filter(speaker=participant, transcript=transcript)

        tbs = process_transcript_by_speaker(participant, transcript, target_child, speaker_utterances, speaker_tokens)
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
    #test3
    TranscriptBySpeaker.objects.bulk_create(TranscriptBySpeaker_store, batch_size=1000) 
    TokenFrequency.objects.bulk_create(TokenFrequency_store, batch_size=1000) 
    print("("+transcript.corpus_name+'/'+transcript.filename+") TranscriptBySpeaker, TokenFrequency bulk calls completed in "+str(round(time.time() - t2, 3))+' seconds')

    return('success')

def process_utterance_tokens(tokens, utterance, token_store, utterance_type, speaker, transcript, target_child):
    #This should modify the token store and utterance object
    from db.models import Token, Utterance
    utt_gloss = []
    utt_stem = []
    utt_relation = []
    utt_pos = []
    utt_num_morphemes = None
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
                relation=relation,
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
            token_store.append(token_record)

        
        # the following are built by iterating through each utterance
    utterance.gloss = ' '.join(utt_gloss)
    utterance.stem = ' '.join(utt_stem)
    utterance.relation = ' '.join(utt_relation)
    utterance.part_of_speech = ' '.join(utt_pos)
    utterance.num_morphemes = utt_num_morphemes
    utterance.num_tokens = len(utt_gloss)                
    utterance.save()