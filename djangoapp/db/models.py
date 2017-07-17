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
    # title = CharField(max_length=255, blank=True, default=None, null=True)  # longer name found in metadata
    # creator = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # subject = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # subject_olac_linguistic_field = CharField(db_column='subject.olac.linguistic.field', max_length=255, blank=True, default=None, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    # subject_olac_language = CharField(db_column='subject.olac.language', max_length=255, blank=True, default=None, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    # subject_childes_participant_age = CharField(db_column='Subject.childes.Participant.age', max_length=255, blank=True, default=None, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    # description = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # publisher = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # contributor = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # date = DateField(max_length=255, blank=True, default=datetime.now(), null=True)
    # type = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # type_olaclinguistic_type = CharField(db_column='type.olaclinguistic-type', max_length=255, blank=True, default=None, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    # type_olacdiscourse_type = CharField(db_column='type.olacdiscourse-type', max_length=255, blank=True, default=None, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    # format = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # identifier = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # language = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # relation = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # coverage = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # rights = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_genre = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_interactivity = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_planningtype = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_involvement = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_socialcontext = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_eventstructure = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_task = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_modalities = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_subject = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_ethnicgroup = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_recordingconditions = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_accessavailability = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_continent = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_country = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_projectdescription = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_mediafiledescription = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    # imdi_writtenresourcesubtype = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.

    class Meta:
        app_label = 'db'
        db_table = 'corpus'


class Participant(Model):
    code = CharField(max_length=255, blank=True, default=None, null=True)
    name = CharField(max_length=255, blank=True, default=None, null=True)  # Field name made lowercase.
    role = CharField(max_length=255, blank=True, default=None, null=True)
    # transcript = ForeignKey(Transcript, blank=True, null=True, default=None)
    corpus = ForeignKey(Corpus, blank=True, null=True, default=None)
    # age = FloatField(blank=True, null=True, default=None)
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
    # exceptions = CharField(max_length=255, blank=True, default=None, null=True)
    # interaction_type = CharField(max_length=255, blank=True, default=None, null=True)
    # location = CharField(max_length=255, blank=True, default=None, null=True)
    # number = CharField(max_length=255, blank=True, default=None, null=True)
    # recording_quality = CharField(max_length=255, blank=True, default=None, null=True)
    # room_layout = CharField(max_length=255, blank=True, default=None, null=True)
    # tape_location = CharField(max_length=255, blank=True, default=None, null=True)
    # time_duration = CharField(max_length=255, blank=True, default=None, null=True)
    # time_start = CharField(max_length=255, blank=True, default=None, null=True)
    # transcription = CharField(max_length=255, blank=True, default=None, null=True)
    # warning = CharField(max_length=255, blank=True, default=None, null=True)
    # activities = CharField(max_length=255, blank=True, default=None, null=True)
    # comment = CharField(max_length=255, blank=True, default=None, null=True)
    date = DateField(max_length=255, blank=True, default=datetime.now, null=True)
    # new_episode = CharField(max_length=255, blank=True, default=None, null=True)
    # new_language = CharField(max_length=255, blank=True, default=None, null=True)
    # page = CharField(max_length=255, blank=True, default=None, null=True)
    # situation = CharField(max_length=255, blank=True, default=None, null=True)
    filename = CharField(max_length=255, blank=True, default=None, null=True)
    target_child = ForeignKey(Participant, blank=True, null=True, default=None)
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

    class Meta:
        app_label = 'db'
        db_table = 'utterance'


# class DependentTier(Model):
#     code = CharField(max_length=255, blank=True, default=None, null=True)
#     line = CharField(max_length=255, blank=True, default=None, null=True)
#     utterance = ForeignKey(Utterance, blank=True, null=True, default=None)
#
#     class Meta:
#         app_label = 'db'
#         db_table = 'dependent_tier'


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

    class Meta:
        app_label = 'db'
        db_table = 'token'




