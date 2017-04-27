# -*- coding: utf-8 -*-
# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey has `on_delete` set to the desired behavior.
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from __future__ import unicode_literals

from django.db import models


class Corpus(models.Model):
    corpus_name = models.CharField(db_column='Corpus_name', max_length=255, blank=True, null=True)
    title = models.CharField(db_column='Title', max_length=255, blank=True, null=True)  # Field name made lowercase.
    creator = models.CharField(db_column='Creator', max_length=255, blank=True, null=True)  # Field name made lowercase.
    subject = models.CharField(db_column='Subject', max_length=255, blank=True, null=True)  # Field name made lowercase.
    subject_olac_linguistic_field = models.CharField(db_column='Subject.olac.linguistic.field', max_length=255, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    subject_olac_language = models.CharField(db_column='Subject.olac.language', max_length=255, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    subject_childes_participant_age = models.CharField(db_column='Subject.childes.Participant.age', max_length=255, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    description = models.CharField(db_column='Description', max_length=255, blank=True, null=True)  # Field name made lowercase.
    publisher = models.CharField(db_column='Publisher', max_length=255, blank=True, null=True)  # Field name made lowercase.
    contributor = models.CharField(db_column='Contributor', max_length=255, blank=True, null=True)  # Field name made lowercase.
    date = models.DateField()
    type = models.CharField(db_column='Type', max_length=255, blank=True, null=True)  # Field name made lowercase.
    type_olaclinguistic_type = models.CharField(db_column='Type.olaclinguistic-type', max_length=255, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    type_olacdiscourse_type = models.CharField(db_column='Type.olacdiscourse-type', max_length=255, blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    format = models.CharField(db_column='Format', max_length=255, blank=True, null=True)  # Field name made lowercase.
    identifier = models.CharField(db_column='Identifier', max_length=255, blank=True, null=True)  # Field name made lowercase.
    language = models.CharField(db_column='Language', max_length=255, blank=True, null=True)  # Field name made lowercase.
    relation = models.CharField(db_column='Relation', max_length=255, blank=True, null=True)  # Field name made lowercase.
    coverage = models.CharField(db_column='Coverage', max_length=255, blank=True, null=True)  # Field name made lowercase.
    rights = models.CharField(db_column='Rights', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_genre = models.CharField(db_column='IMDI_Genre', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_interactivity = models.CharField(db_column='IMDI_Interactivity', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_planningtype = models.CharField(db_column='IMDI_PlanningType', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_involvement = models.CharField(db_column='IMDI_Involvement', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_socialcontext = models.CharField(db_column='IMDI_SocialContext', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_eventstructure = models.CharField(db_column='IMDI_EventStructure', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_task = models.CharField(db_column='IMDI_Task', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_modalities = models.CharField(db_column='IMDI_Modalities', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_subject = models.CharField(db_column='IMDI_Subject', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_ethnicgroup = models.CharField(db_column='IMDI_EthnicGroup', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_recordingconditions = models.CharField(db_column='IMDI_RecordingConditions', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_accessavailability = models.CharField(db_column='IMDI_AccessAvailability', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_continent = models.CharField(db_column='IMDI_Continent', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_country = models.CharField(db_column='IMDI_Country', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_projectdescription = models.CharField(db_column='IMDI_ProjectDescription', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_mediafiledescription = models.CharField(db_column='IMDI_MediaFileDescription', max_length=255, blank=True, null=True)  # Field name made lowercase.
    imdi_writtenresourcesubtype = models.CharField(db_column='IMDI_WrittenResourceSubType', max_length=255, blank=True, null=True)  # Field name made lowercase.
    target_child = models.CharField(db_column='Child', max_length=255, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        db_table = 'corpus'


class Child(models.Model):
    name = models.CharField(db_column='Name', max_length=25, blank=True, null=True)  # Field name made lowercase.
    primary_gender = models.CharField(db_column='Primary_Gender', max_length=25, blank=True, null=True)  # Field name made lowercase.
    min_age = models.IntegerField(blank=True, null=True)
    max_age = models.IntegerField(blank=True, null=True)
    corpus = models.ForeignKey(Corpus, blank=True, null=True)

    class Meta:
        db_table = 'child'


class Session(models.Model):
    filename = models.TextField(blank=True, null=True)
    participants = models.TextField(blank=True, null=True) # Many to many?...
    date = models.DateField()
    child = models.ForeignKey(Child, blank=True, null=True)

    class Meta:
        db_table = 'session'


class Utterance(models.Model):
    speaker = models.TextField(blank=True, null=True)
    act = models.TextField(blank=True, null=True)
    gpx = models.TextField(blank=True, null=True)
    sit = models.TextField(blank=True, null=True)
    utterance_order = models.IntegerField(blank=True, null=True)
    sent_gloss = models.TextField(blank=True, null=True)
    session = models.ForeignKey(Session)

    class Meta:
        db_table = 'utterance'


class Word(models.Model):
    gloss = models.TextField(blank=True, null=True)
    mor = models.TextField(blank=True, null=True)
    gra = models.TextField(blank=True, null=True) # New field
    xgra = models.TextField(blank=True, null=True)  # New field
    utterance = models.ForeignKey(Utterance)
    attags = models.TextField(blank=True, null=True)
    speaker = models.TextField(blank=True, null=True)
    act = models.TextField(blank=True, null=True)
    gpx = models.TextField(blank=True, null=True)
    sit = models.TextField(blank=True, null=True)
    com = models.TextField(blank=True, null=True)
    par = models.TextField(blank=True, null=True)
    filename = models.TextField(blank=True, null=True)
    participants = models.TextField(blank=True, null=True)
    date = models.TextField(blank=True, null=True)
    language = models.TextField(blank=True, null=True)
    corpus = models.TextField(blank=True, null=True)
    age = models.FloatField(blank=True, null=True)
    gender = models.TextField(blank=True, null=True)
    utt_number = models.TextField(blank=True, null=True)
    sentgloss = models.TextField(blank=True, null=True)
    sentmor = models.TextField(blank=True, null=True)
    child = models.TextField(blank=True, null=True)
    add = models.TextField(blank=True, null=True)
    alt = models.TextField(blank=True, null=True)
    int = models.TextField(blank=True, null=True)
    spa = models.TextField(blank=True, null=True)
    err = models.TextField(blank=True, null=True)
    eng = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'word'


"""
These tables are not being added to the database for now.
"""

class ChildesChiFreq(models.Model):
    index = models.BigIntegerField(blank=True, null=True)
    word = models.CharField(max_length=63, blank=True, null=True)
    frequency = models.BigIntegerField(blank=True, null=True)
    in_mcdi = models.IntegerField(blank=True, null=True)
    all_aoa = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'childes_chi_freq'


class ChildesChiLongFreq(models.Model):
    index = models.BigIntegerField(blank=True, null=True)
    word = models.CharField(max_length=63, blank=True, null=True)
    age = models.FloatField(blank=True, null=True)
    frequency = models.BigIntegerField(blank=True, null=True)
    in_mcdi = models.IntegerField(blank=True, null=True)
    all_aoa = models.FloatField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'childes_chi_long_freq'


class Modifiedchi(models.Model):
    row_names = models.TextField(blank=True, null=True)
    gloss = models.TextField(blank=True, null=True)
    mor = models.TextField(blank=True, null=True)
    attags = models.TextField(blank=True, null=True)
    speaker = models.TextField(blank=True, null=True)
    act = models.TextField(blank=True, null=True)
    gpx = models.TextField(blank=True, null=True)
    sit = models.TextField(blank=True, null=True)
    com = models.TextField(blank=True, null=True)
    par = models.TextField(blank=True, null=True)
    filename = models.TextField(blank=True, null=True)
    participants = models.TextField(blank=True, null=True)
    date = models.TextField(blank=True, null=True)
    language = models.TextField(blank=True, null=True)
    corpus = models.TextField(blank=True, null=True)
    age = models.FloatField(blank=True, null=True)
    gender = models.TextField(blank=True, null=True)
    utt_number = models.TextField(db_column='utt.number', blank=True, null=True)  # Field renamed to remove unsuitable characters.
    sentgloss = models.TextField(blank=True, null=True)
    sentmor = models.TextField(blank=True, null=True)
    add = models.TextField(blank=True, null=True)
    alt = models.TextField(blank=True, null=True)
    int = models.TextField(blank=True, null=True)
    spa = models.TextField(blank=True, null=True)
    err = models.TextField(blank=True, null=True)
    eng = models.TextField(blank=True, null=True)
    age_mo = models.FloatField(blank=True, null=True)
    child = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'modifiedchi'

