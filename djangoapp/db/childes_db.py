from models import Collection, Transcript, Participant, Utterance, Token, Corpus
import multiprocessing
import re
import logging
import os
import traceback
from django import db

def truncate():
    Token.objects.all().delete()
    Utterance.objects.all().delete()
    Participant.objects.all().delete()
    Transcript.objects.all().delete()
    Corpus.objects.all().delete()
    Collection.objects.all().delete()

def migrate():
    from childes import CHILDESCorpusReader

    multiprocessing.log_to_stderr()
    logger = multiprocessing.get_logger()
    logger.setLevel(logging.INFO)

    pool = multiprocessing.Pool()
    results = []

    root = '/home/alsan/corpora/childes-xml/'

    for collection_name in os.listdir(root):
        if collection_name == 'Spanish':
            continue

        corpus_root = root + collection_name
        collection = Collection.objects.create(name=collection_name)

        for corpus_name in os.listdir(corpus_root):
            print corpus_name
            nltk_corpus = CHILDESCorpusReader(corpus_root, corpus_name + '/.*.xml')
            corpus = Corpus.objects.create(name=corpus_name, collection=collection)

            # Iterate over all transcripts in this corpus
            for fileid in nltk_corpus.fileids():
                # Create transcript and participant objects up front
                transcript, participants, target_child = create_transcript_and_participants(nltk_corpus, fileid, corpus)

                # necessary so child process doesn't inherit file descriptor
                db.connections.close_all()

                # Create utterance and token objects asynchronously
                results.append(pool.apply_async(process_utterances, args=(nltk_corpus, fileid, transcript, participants, target_child)))

    pool.close()

    # catch any exceptions thrown by child processes
    for result in results:
        try:
            result.get()
        except:
            traceback.print_exc()

def create_transcript_and_participants(nltk_corpus, fileid, corpus):
    # Create transcript object
    metadata = nltk_corpus.corpus(fileid)[0]

    transcript = Transcript.objects.create(
        filename=fileid,
        corpus=corpus,
        languages=metadata.get('Lang'),
        date=metadata.get('Date')
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

        target_child.save()
        transcript.save()

        result_participants.append(target_child)

    # Save all other participants
    for nltk_participant in nltk_participants.values():
        participant = get_or_create_participant(corpus, nltk_participant, target_child)
        result_participants.append(participant)

    return transcript, result_participants, target_child


def process_utterances(nltk_corpus, fileid, transcript, participants, target_child):

    sents = nltk_corpus.get_custom_sents(fileid)
    for sent in sents:
        # TODO use map instead of tuple
        uID = int(sent[0].replace("u", "")) + 1
        speaker_code = sent[1]
        tokens = sent[2]

        # TODO use map code: participant object
        for participant in participants:
            if participant.code == speaker_code:
                speaker = participant

        if not speaker:
            raise Exception('code not found in participant array: %s, transcript id %s' % (str(speaker_code), str(transcript.pk)))

        utterance = Utterance.objects.create(
            speaker=speaker,
            transcript=transcript,
            order=uID,
            corpus=transcript.corpus,
            speaker_code=speaker.code,
            speaker_name=speaker.name,
            speaker_age=speaker.age,
            speaker_role=speaker.role,
            speaker_sex=speaker.sex,
            target_child=target_child,
            target_child_name=target_child.name if target_child else None,
            target_child_age=target_child.age if target_child else None,
            target_child_sex=target_child.sex if target_child else None
        )

        utt_gloss = []
        utt_stem = []
        utt_relation = []
        utt_pos = []

        # TODO nltk token instead of token
        for token in tokens:
            # TODO use null or blank?
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

            Token.objects.create(
                gloss=gloss,
                replacement=replacement,
                stem=stem,
                part_of_speech=part_of_speech,
                relation=relation,
                token_order=token_order,
                speaker=speaker,
                utterance=utterance,
                transcript=transcript,
                corpus=transcript.corpus,
                speaker_code=speaker.code,
                speaker_name=speaker.name,
                speaker_age=speaker.age,
                speaker_role=speaker.role,
                speaker_sex=speaker.sex,
                target_child=target_child,
                target_child_name=target_child.name if target_child else None,
                target_child_age=target_child.age if target_child else None,
                target_child_sex=target_child.sex if target_child else None
            )

        utterance.gloss = ' '.join(utt_gloss)
        utterance.stem = ' '.join(utt_stem)
        utterance.relation = ' '.join(utt_relation)
        utterance.part_of_speech = ' '.join(utt_pos)
        utterance.length = len(utt_gloss)
        utterance.save()

def extract_target_child(participants):
    nltk_target_child = None
    code_to_pop = None

    for code, nltk_participant in participants.iteritems():
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
            age_in_days += number * 30
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

    query_set = Participant.objects.filter(code=code, name=name, role=role, corpus=corpus)

    # Filter participant candidates by target child
    if target_child:
        query_set = query_set.filter(target_child=target_child)

    participant = query_set.first()

    if not participant:
        participant = Participant(
            code=code,
            name=name,
            role=role,
            language=language,
            group=group,
            sex=sex,
            ses=ses,
            education=education,
            custom=custom,
            corpus=corpus
        )
        if target_child:
            participant.target_child = target_child

    update_age(participant, age)

    # TODO very confusing. in memory attribute gets passed to child process
    # Mark the age for this participant for this transcript, to be saved in utterance / token as speaker_age
    participant.age = age

    participant.save()

    return participant
