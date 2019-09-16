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
#from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker
import db.models


from db.lexical_diversity import mtld, hdd
from db.childes import CHILDESCorpusReader

import functools
import numpy as np
import sys
import pdb

def trace_unhandled_exceptions(func):
    @functools.wraps(func)
    def wrapped_func(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except:
            print('Exception in '+func.__name__)
            traceback.print_exc()
    return(wrapped_func)

def populate_db(collection_root, selected_collection=None, parallelize=False):    

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

    # catch any exceptions thrown by child processes        
    for result in results:
        try:
            result.get()
        except:
            traceback.print_exc()

def process_collection(collection_root, collection_name, pool, parallelize=False):
    
    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker

    print('Processing collection '+collection_name+' at '+os.path.join(collection_root, collection_name))    
    t0 = time.time()
    collection = Collection.objects.create(name=collection_name)

    results = []

    # the top level of a collection is the corpora    
    top_level_corpora_in_collection = [os.path.basename(os.path.normpath(x)) for x in glob.glob(os.path.join(collection_root, collection_name,'*/')) ]       

    print('Corpus contains '+str(len(top_level_corpora_in_collection)) + ' top-level corpora; parallelizing...')

    # apply_async
    for corpus_name in top_level_corpora_in_collection:
        
        
        if parallelize:
            # multicore
            results.append(pool.apply_async(process_corpus, args =(os.path.join(collection_root, collection_name), corpus_name, collection_name)))
        
        else:
            # single core for debugging
            results.append(process_corpus(os.path.join(collection_root, collection_name), corpus_name, collection_name))


    # catch any exceptions thrown by child processes            
    for result in results:
        try:
            result.get()

        except:
            traceback.print_exc()

    # dumb parallelization
    #results = Parallel(n_jobs=24)(delayed(process_corpus)(os.path.join(collection_root, collection_name), corpus_name, collection_name) for corpus_name in top_level_corpora_in_collection)

    print('Finished collection '+collection_name +' in '+str(round(time.time() - t0, 3))+' seconds')
    return(result)

def bulk_write(records_to_write, data_type, corpus_name, batch_size=1000):

    bulk_write_start_time = time.time()    
    getattr(db.models, data_type).objects.bulk_create(records_to_write, batch_size)
    print('('+corpus_name+') Bulk write for '+data_type+' took '+str(round(time.time() - bulk_write_start_time, 3)))+'s'

        
def process_corpus(corpus_root, corpus_name, collection_name):
    
    import django
    django.setup()
    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker

    # retrieve the Collection from within the process so we don't need to pass the Django ORM object, which is unpickleable
    collection = Collection.objects.get(name = collection_name)
    corpus_path = os.path.join(corpus_root, corpus_name)

    print('Processing corpus '+corpus_name+' at '+corpus_path)

    process_utterance_results = []

    dirs_with_xml = []
    for root, dirs, files in os.walk(os.path.join(corpus_root, corpus_name)):
        for file in files:
            if file.endswith(".xml"):
                dirs_with_xml.append(root)
    dirs_with_xml = np.unique(dirs_with_xml)

    print('('+corpus_name+') Number of sub-directories in corpus: '+str(len(dirs_with_xml)))

    for dir_with_xml in dirs_with_xml:

        print('('+corpus_name+') Processing XML directory: '+dir_with_xml)
        
        nltk_corpus = CHILDESCorpusReader(dir_with_xml, '.*.xml')        
        corpus = Corpus.objects.create(name=corpus_name, collection=collection, collection_name=collection.name)

        # Iterate over all transcripts in this corpus        
        for fileid in nltk_corpus.fileids():

            # Create transcript and participant objects up front
            transcript, participants, target_child = create_transcript_and_participants(nltk_corpus, fileid, corpus,
                                                                                        collection)

            # Ignore old filenames (due to recent update)
            if not transcript:
                continue

            # necessary so child process doesn't inherit file descriptor
            #db.connections.close_all()

            # Create utterance and token objects asynchronously
            process_utterance_results.append(process_utterances(nltk_corpus, fileid, transcript, participants,
                target_child))
        

        print('('+corpus_name+') Finished directory '+dir_with_xml)

    print(process_utterance_results)
    print('Finished corpus!')    

def flatten_list(hierarchical_list, list_name = None):    
    # list_name is for debugging
    if list_name is not None:
        print('Flattening '+list_name+' ('+str(len(list_name))+' objects)...')
        print('Example record:')
        print(hierarchical_list)

    return([item for sublist in hierarchical_list for item in sublist if item is not None])

def create_transcript_and_participants(nltk_corpus, fileid, corpus, collection):
    
    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker

    # Create transcript object
    metadata = nltk_corpus.corpus(fileid)[0]

    # Return immediately if transcript has already been parsed
    pid = metadata.get('PID')
    if Transcript.objects.filter(pid=pid).exists():
        return None, None, None

    transcript = Transcript.objects.create(
        filename=fileid,
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
        target_child = get_or_create_participant(corpus, nltk_target_child)

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
        participant = get_or_create_participant(corpus, nltk_participant, target_child)
        result_participants.append(participant)

    result_participants = [x for x in result_participants if x is not None]

    return transcript, result_participants, target_child


def process_utterances(nltk_corpus, fileid, transcript, participants, target_child):

    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker
    
    utterance_store = []
    token_store = []
    sents = nltk_corpus.get_custom_sents(fileid)
    
    #utterance_store = {}

    for sent in sents:

        # TODO use map instead of tuple
        uID = int(sent[0].replace("u", "")) + 1
        speaker_code = sent[1]
        terminator = sent[2]
        # annotations = sent[3]
        media = sent[4]
        tokens = sent[5]

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
        # utt_relation = []
        utt_pos = []
        utt_num_morphemes = None

        # TODO nltk token instead of token        
        for token in tokens:
            # TODO use null or blank?
            gloss = token.get('gloss', '')
            replacement = token.get('replacement', '')
            stem = token.get('stem', '')
            part_of_speech = token.get('pos', '')
            # relation = token.get('relation', '')
            token_order = token.get('order', '')

            prefix = token.get('prefix', '')
            suffix = token.get('suffix', '')
            english = token.get('english', '')
            clitic = token.get('clitic', '')
            num_morphemes = token.get('morpheme_length')

            if gloss:
                utt_gloss.append(gloss)

            if stem:
                utt_stem.append(stem)

            # if relation:
            #     utt_relation.append(relation)

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
                part_of_speech=part_of_speech,
                utterance_type=utterance_type,
                num_morphemes = num_morphemes,
                # relation=relation,
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
        # utterance.relation = ' '.join(utt_relation)
        utterance.part_of_speech = ' '.join(utt_pos)
        utterance.num_morphemes = utt_num_morphemes
        utterance.num_tokens = len(utt_gloss)        
        utterance.save()

    
    t1 = time.time()
    #bulk_write(token_store, 'Token', transcript.corpus.name, batch_size=1000)
    #bulk_write(utterance_store, 'Utterance', transcript.corpus.name, batch_size=1000)
    #Utterance.objects.bulk_create(utterance_store.values(), batch_size=1000) 
    Token.objects.bulk_create(token_store, batch_size=1000) # utterance is none by the time we are here    
    print("("+transcript.corpus_name+'/'+transcript.filename+") Token, utterance bulk calls completed in "+str(round(time.time() - t1, 3))+' seconds')


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
    #bulk_write(TranscriptBySpeaker_store, 'TranscriptBySpeaker', transcript.corpus.name, batch_size=1000)
    #bulk_write(TokenFrequency_store, 'TokenFrequency', transcript.corpus.name, batch_size=1000)
    TranscriptBySpeaker.objects.bulk_create(TranscriptBySpeaker_store, batch_size=1000) 
    TokenFrequency.objects.bulk_create(TokenFrequency_store, batch_size=1000) 
    print("("+transcript.corpus_name+'/'+transcript.filename+") TrasncriptBySpeaker, TokenFrequency bulk calls completed in "+str(round(time.time() - t2, 3))+' seconds')

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


def get_or_create_participant(corpus, attr_map, target_child=None):
    
    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker

    if not attr_map:
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
    query_set = Participant.objects.filter(code=code, name=name, role=role, corpus=corpus)

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
