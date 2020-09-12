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

def create_transcript_and_participants(dir_with_xml, nltk_corpus, fileid, corpus, collection):
    
    from db.models import Collection, Transcript, Participant, Utterance, Token, Corpus, TokenFrequency, TranscriptBySpeaker

    # Create transcript object
    metadata = nltk_corpus.corpus(fileid)[0]

    # Return immediately if transcript has already been parsed
    pid = metadata.get('PID')
    if Transcript.objects.filter(pid=pid).exists():
        return None, None, None

    # check the whether os.path.join(corpus, fileId) is what we expect

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
