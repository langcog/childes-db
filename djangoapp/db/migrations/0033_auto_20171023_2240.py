# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-10-23 22:40
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0032_auto_20171023_2147'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='token',
            name='relation',
        ),
        migrations.RemoveField(
            model_name='utterance',
            name='relation',
        ),
        migrations.AddField(
            model_name='token',
            name='length',
            field=models.CharField(blank=True, default=None, max_length=255, null=True),
        ),
    ]