# -*- coding: utf-8 -*-
# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange  order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the  but don't rename db_table values or field names.
from __future__ import unicode_literals

from django.db.models import Model, CharField, ForeignKey, IntegerField, DateField

class Collection(Model):
    name = CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'db' # should we keep app label???
        db_table = 'collection'


class Corpus(Model):
    name = CharField(max_length=255, blank=True) # simple name
    collection = ForeignKey(Collection, blank=True, null=True)
    title = CharField(max_length=255, blank=True)  # longer name found in metadata
    creator = CharField(max_length=255, blank=True)  # Field name made lowercase.
    subject = CharField(max_length=255, blank=True)  # Field name made lowercase.
    subject_olac_linguistic_field = CharField(db_column='subject.olac.linguistic.field', max_length=255, blank=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    subject_olac_language = CharField(db_column='subject.olac.language', max_length=255, blank=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    subject_childes_participant_age = CharField(db_column='Subject.childes.Participant.age', max_length=255, blank=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    description = CharField(max_length=255, blank=True)  # Field name made lowercase.
    publisher = CharField(max_length=255, blank=True)  # Field name made lowercase.
    contributor = CharField(max_length=255, blank=True)  # Field name made lowercase.
    date = DateField(max_length=255, blank=True)
    type = CharField(max_length=255, blank=True)  # Field name made lowercase.
    type_olaclinguistic_type = CharField(db_column='type.olaclinguistic-type', max_length=255, blank=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    type_olacdiscourse_type = CharField(db_column='type.olacdiscourse-type', max_length=255, blank=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    format = CharField(max_length=255, blank=True)  # Field name made lowercase.
    identifier = CharField(max_length=255, blank=True)  # Field name made lowercase.
    language = CharField(max_length=255, blank=True)  # Field name made lowercase.
    relation = CharField(max_length=255, blank=True)  # Field name made lowercase.
    coverage = CharField(max_length=255, blank=True)  # Field name made lowercase.
    rights = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_genre = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_interactivity = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_planningtype = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_involvement = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_socialcontext = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_eventstructure = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_task = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_modalities = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_subject = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_ethnicgroup = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_recordingconditions = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_accessavailability = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_continent = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_country = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_projectdescription = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_mediafiledescription = CharField(max_length=255, blank=True)  # Field name made lowercase.
    imdi_writtenresourcesubtype = CharField(max_length=255, blank=True)  # Field name made lowercase.

    class Meta:
        app_label = 'db'
        db_table = 'corpus'

class Transcript(Model):
    corpus = ForeignKey(Corpus, blank=True, null=True)
    languages = CharField(max_length=255, blank=True)
    exceptions = CharField(max_length=255, blank=True)
    interaction_type = CharField(max_length=255, blank=True)
    location = CharField(max_length=255, blank=True)
    number = CharField(max_length=255, blank=True)
    recording_quality = CharField(max_length=255, blank=True)
    room_layout = CharField(max_length=255, blank=True)
    tape_location = CharField(max_length=255, blank=True)
    time_duration = CharField(max_length=255, blank=True)
    time_start = CharField(max_length=255, blank=True)
    transcription = CharField(max_length=255, blank=True)
    warning = CharField(max_length=255, blank=True)
    activities = CharField(max_length=255, blank=True)
    comment = CharField(max_length=255, blank=True)
    date = DateField(max_length=255, blank=True)
    new_episode = CharField(max_length=255, blank=True)
    new_language = CharField(max_length=255, blank=True)
    page = CharField(max_length=255, blank=True)
    situation = CharField(max_length=255, blank=True)
    filename = CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'db'
        db_table = 'transcript'


class Participant(Model):
    code = CharField(max_length=255, blank=True)
    name = CharField(max_length=255, blank=True)  # Field name made lowercase.
    role = CharField(max_length=255, blank=True)
    transcript = ForeignKey(Transcript, blank=True, null=True)
    corpus = ForeignKey(Corpus, blank=True, null=True)
    age = IntegerField(blank=True, null=True)
    language = CharField(max_length=255, blank=True)
    group = CharField(max_length=255, blank=True)
    gender = CharField(max_length=255, blank=True)  # Field name made lowercase.
    ses = CharField(max_length=255, blank=True) # expand out SES?
    education = CharField(max_length=255, blank=True)
    custom = CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'db'
        db_table = 'participant'


class Utterance(Model):
    speaker = ForeignKey(Participant, blank=True, null=True)
    transcript = ForeignKey(Transcript, blank=True, null=True)
    order = IntegerField(blank=True, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'utterance'


class DependentTier(Model):
    code = CharField(max_length=255, blank=True)
    line = CharField(max_length=255, blank=True)
    utterance = ForeignKey(Utterance, blank=True, null=True)

    class Meta:
        app_label = 'db'
        db_table = 'dependent_tier'


class Token(Model):
    gloss = CharField(max_length=255, blank=True)
    speaker = ForeignKey(Participant, blank=True, null=True)
    utterance = ForeignKey(Utterance, blank=True, null=True)
    replacement = CharField(max_length=255, blank=True)
    stem = CharField(max_length=255, blank=True)
    part_of_speech = CharField(max_length=255, blank=True)
    relation = CharField(max_length=255, blank=True)

    class Meta:
        app_label = 'db'
        db_table = 'token'



