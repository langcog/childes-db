from __future__ import unicode_literals

from django.db.models import Model, CharField, ForeignKey, IntegerField, DateField, TextField, FloatField, BooleanField
from datetime import datetime
from django.db.models import DO_NOTHING

class Collection(Model):
    name = CharField(max_length=255, blank=True, default=None, null=True)
    data_source = CharField(max_length=255, blank=True, default=None, null=True)
    
    class Meta:
        app_label = 'db' # should we keep app label?
        db_table = 'collection'


class Corpus(Model):
    name = CharField(max_length=255, blank=True, default=None, null=True) # simple name
    collection = ForeignKey(Collection, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    collection_name = CharField(max_length=255, blank=True, default=None, null=True)
    data_source = CharField(max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'corpus'


class Participant(Model):
    code = CharField(max_length=255, blank=True, default=None, null=True)
    name = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    role = CharField(max_length=255, blank=True, default=None, null=True)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    corpus_name = CharField(max_length=255, blank=True, default=None, null=True)
    min_age = FloatField(blank=True, null=True, default=None)
    max_age = FloatField(blank=True, null=True, default=None)
    language = CharField(max_length=255, blank=True, default=None, null=True)
    group = CharField(max_length=255, blank=True, default=None, null=True)
    sex = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    ses = CharField(max_length=255, blank=True, default=None, null=True) # expand out SES?
    education = CharField(max_length=255, blank=True, default=None, null=True)
    custom = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey('self', blank=True, null=True, default=None, on_delete=DO_NOTHING)
    collection = ForeignKey(Collection, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    collection_name = CharField(max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'participant'


class Transcript(Model):
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    corpus_name = CharField(max_length=255, blank=True, default=None, null=True)
    language = CharField(max_length=255, blank=True, default=None, null=True)
    date = DateField(max_length=255, blank=True, default=datetime.now, null=True)
    filename = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    target_child_name = CharField(max_length=255, blank=True, default=None, null=True)
    target_child_age = FloatField(blank=True, null=True, default=None)
    target_child_sex = CharField(max_length=255, blank=True, default=None, null=True)
    collection = ForeignKey(Collection, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    collection_name = CharField(max_length=255, blank=True, default=None, null=True)
    pid = CharField(max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'transcript'


class Utterance(Model):
    gloss = CharField(db_index=True, max_length=1023, blank=True, default=None, null=True)
    stem = CharField(db_index=True, max_length=1023, blank=True, default=None, null=True)
    #relation = TextField(blank=True, default=None, null=True)
    actual_phonology = CharField(db_index=True, max_length=1023, blank=True, default=None, null=True)
    model_phonology = CharField(db_index=True, max_length=1023, blank=True, default=None, null=True)
    type = CharField(max_length=255, blank=True, default=None, null=True)
    speaker = ForeignKey(Participant, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    language = CharField(max_length=255, blank=True, default=None, null=True)
    num_morphemes = IntegerField(blank=True, null=True, default=None)
    num_tokens = IntegerField(blank=True, null=True, default=None)
    transcript = ForeignKey(Transcript, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    utterance_order = IntegerField(blank=True, null=True, default=None)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    corpus_name = CharField(max_length=255, blank=True, default=None, null=True)
    part_of_speech = TextField(blank=True, default=None, null=True)
    speaker_code = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_name = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_role = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None, related_name="related_utterances", on_delete=DO_NOTHING)
    target_child_name = CharField(max_length=255, blank=True, default=None, null=True)
    target_child_age = FloatField(db_index=True, blank=True, null=True, default=None)
    target_child_sex = CharField(max_length=255, blank=True, default=None, null=True)
    media_start = FloatField(blank=True, null=True, default=None)
    media_end = FloatField(blank=True, null=True, default=None)
    media_unit = CharField(max_length=255, blank=True, default=None, null=True)
    collection = ForeignKey(Collection, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    collection_name = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)


    class Meta:
        app_label = 'db'
        db_table = 'utterance'


class Token(Model):
    gloss = CharField(db_index=True, max_length=511, blank=True, default=None, null=True)
    speaker = ForeignKey(Participant, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    language = CharField(max_length=255, blank=True, default=None, null=True)
    token_order = IntegerField(blank=True, null=True, default=None)
    utterance = ForeignKey(Utterance, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    #head = ForeignKey(to='Token', null=True, related_name='token_head', on_delete=DO_NOTHING)
    #relation_to_head = CharField(max_length=255, blank=True, default=None, null=True)
    #dependent = ForeignKey(to='Token', null=False, related_name='token_dependent', on_delete=DO_NOTHING) # one to many relationship
    replacement = CharField(max_length=255, blank=True, default=None, null=True)
    prefix = CharField(max_length=255, blank=True, default=None, null=True)
    part_of_speech = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)
    stem = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)
    #relation = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)
    actual_phonology = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)
    model_phonology = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)
    suffix = CharField(max_length=255, blank=True, default=None, null=True)
    num_morphemes = IntegerField(blank=True, null=True, default=None)
    english = CharField(max_length=255, blank=True, default=None, null=True)
    clitic = CharField(max_length=255, blank=True, default=None, null=True)
    utterance_type = CharField(max_length=255, blank=True, default=None, null=True)
    transcript = ForeignKey(Transcript, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    corpus_name = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_code = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_name = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_role = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None, related_name="related_tokens", on_delete=DO_NOTHING)
    target_child_name = CharField(max_length=255, blank=True, default=None, null=True)
    target_child_age = FloatField(db_index=True, blank=True, null=True, default=None)
    target_child_sex = CharField(max_length=255, blank=True, default=None, null=True)
    collection = ForeignKey(Collection, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    collection_name = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'token'


class TokenFrequency(Model):
    transcript = ForeignKey(Transcript, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    gloss = CharField(db_index=True, max_length=511, blank=True, default=None, null=True)
    count = IntegerField(db_index=True, blank=True, null=True, default=None)
    speaker = ForeignKey(Participant, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    speaker_role = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)
    language = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None, related_name="related_token_frequencies", on_delete=DO_NOTHING)
    target_child_name = CharField(max_length=255, blank=True, default=None, null=True)
    target_child_age = FloatField(db_index=True, blank=True, null=True, default=None)
    target_child_sex = CharField(max_length=255, blank=True, default=None, null=True)
    collection = ForeignKey(Collection, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    collection_name = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'token_frequency'


class TranscriptBySpeaker(Model):
    transcript = ForeignKey(Transcript, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    speaker = ForeignKey(Participant, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    speaker_role = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)
    language = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None, related_name="related_transcript_statistics", on_delete=DO_NOTHING)
    target_child_name = CharField(max_length=255, blank=True, default=None, null=True)
    target_child_age = FloatField(db_index=True, blank=True, null=True, default=None)
    target_child_sex = CharField(max_length=255, blank=True, default=None, null=True)
    num_utterances = IntegerField(blank=True, null=True, default=None)
    mlu_w = FloatField(blank=True, null=True, default=None)
    mlu_m = FloatField(blank=True, null=True, default=None)
    mtld = FloatField(blank=True, null=True, default=None)
    hdd = FloatField(blank=True, null=True, default=None)
    num_types = IntegerField(blank=True, null=True, default=None)
    num_tokens = IntegerField(blank=True, null=True, default=None)
    num_morphemes = IntegerField(blank=True, null=True, default=None)
    collection = ForeignKey(Collection, blank=True, null=True, default=None, on_delete=DO_NOTHING)
    collection_name = CharField(db_index=True, max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'transcript_by_speaker'


class Admin(Model):
    date = DateField(max_length=255, blank=True, default=datetime.now, null=True)
    version = CharField(max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'admin'


for model_class in (Token, Utterance, TokenFrequency, TranscriptBySpeaker, Admin, Transcript, Participant, Corpus, Collection):
    globals()[model_class] = model_class
