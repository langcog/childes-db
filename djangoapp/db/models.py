# -*- coding: utf-8 -*-
# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange  order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the  but don't rename db_table values or field names.
from __future__ import unicode_literals

from django.db.models import Model, CharField, ForeignKey, IntegerField, DateField, TextField, FloatField
from datetime import datetime

class Collection(Model):
    name = CharField(max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db' # should we keep app label?
        db_table = 'collection'


class Corpus(Model):
    name = CharField(max_length=255, blank=True, default=None, null=True) # simple name
    collection = ForeignKey(Collection, blank=True, null=True, default=None)

    class Meta:
        app_label = 'db'
        db_table = 'corpus'


class Participant(Model):
    code = CharField(max_length=255, blank=True, default=None, null=True)
    name = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    role = CharField(max_length=255, blank=True, default=None, null=True)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None)
    min_age = FloatField(blank=True, null=True, default=None)
    max_age = FloatField(blank=True, null=True, default=None)
    language = CharField(max_length=255, blank=True, default=None, null=True)
    group = CharField(max_length=255, blank=True, default=None, null=True)
    sex = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    ses = CharField(max_length=255, blank=True, default=None, null=True) # expand out SES?
    education = CharField(max_length=255, blank=True, default=None, null=True)
    custom = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey('self', blank=True, null=True, default=None)

    class Meta:
        app_label = 'db'
        db_table = 'participant'


class Transcript(Model):
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None)
    languages = CharField(max_length=255, blank=True, default=None, null=True)
    date = DateField(max_length=255, blank=True, default=datetime.now, null=True)
    filename = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None)
    target_child_name = CharField(max_length=255, blank=True, default=None, null=True)
    target_child_age = FloatField(blank=True, null=True, default=None)

    class Meta:
        app_label = 'db'
        db_table = 'transcript'


class Utterance(Model):
    gloss = TextField(blank=True, default=None, null=True)
    stem = TextField(blank=True, default=None, null=True)
    relation = TextField(blank=True, default=None, null=True)
    speaker = ForeignKey(Participant, blank=True, null=True, default=None)
    length = IntegerField(blank=True, null=True, default=None)
    transcript = ForeignKey(Transcript, blank=True, null=True, default=None)
    order = IntegerField(blank=True, null=True, default=None)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None)
    part_of_speech = TextField(blank=True, default=None, null=True)
    speaker_code = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_name = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_age = FloatField(blank=True, null=True, default=None)
    speaker_role = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_sex = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None, related_name="all_related_utterances")
    target_child_name = CharField(max_length=255, blank=True, default=None, null=True)
    target_child_age = FloatField(db_index=True, blank=True, null=True, default=None)
    target_child_sex = CharField(max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'utterance'


class Token(Model):
    gloss = CharField(max_length=255, blank=True, default=None, null=True)
    speaker = ForeignKey(Participant, blank=True, null=True, default=None)
    token_order = IntegerField(blank=True, null=True, default=None)
    utterance = ForeignKey(Utterance, blank=True, null=True, default=None)
    replacement = CharField(max_length=255, blank=True, default=None, null=True)
    stem = CharField(max_length=255, blank=True, default=None, null=True)
    part_of_speech = CharField(max_length=255, blank=True, default=None, null=True)
    relation = CharField(max_length=255, blank=True, default=None, null=True)
    transcript = ForeignKey(Transcript, blank=True, null=True, default=None)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None)
    speaker_code = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_name = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_age = FloatField(blank=True, null=True, default=None)
    speaker_role = CharField(max_length=255, blank=True, default=None, null=True)
    speaker_sex = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None, related_name="all_related_tokens")
    target_child_name = CharField(max_length=255, blank=True, default=None, null=True)
    target_child_age = FloatField(db_index=True, blank=True, null=True, default=None)
    target_child_sex = CharField(max_length=255, blank=True, default=None, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'token'
