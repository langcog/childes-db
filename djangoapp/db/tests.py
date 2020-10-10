# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import json
from django.test import TestCase
from models import Token
from django.conf import settings

BY_SPEAKER = True
JSON_FILENAME = 'db/scripts/clan_counts' + ('_by_speaker.json' if BY_SPEAKER else '.json')

class TestSequence(TestCase):
    pass

def test_generator(a, b):
    def test(self):
        self.assertEqual(a,b)
    return test

with open(os.path.join(settings.BASE_DIR, JSON_FILENAME)) as clan_counts_file:
    clan_counts = json.load(clan_counts_file)

for corpus_name, clan_count in clan_counts.items():
    print corpus_name
    if BY_SPEAKER:
        corpus_name, speaker_code = corpus_name.split('_')
        db_total = Token.objects.filter(corpus__name=corpus_name, speaker_code=speaker_code).exclude(part_of_speech__exact='').count()
        test_method_name = 'test_unigrams_{}_{}'.format(corpus_name, speaker_code)
    else:
        db_total = Token.objects.filter(corpus__name=corpus_name).exclude(part_of_speech__exact='').count()
        test_method_name = 'test_unigrams_{}'.format(corpus_name)

    test_method = test_generator(clan_count, db_total)
    setattr(TestSequence, test_method_name, test_method)

