from xml.dom import minidom
from nltk.corpus.reader.xmldocs import XMLCorpusReader, ElementTree
import re
import time
from django.db import transaction
import logging

def bulk_write(token_store, transcript, Token):
    t1 = time.time()        
    with transaction.atomic():
        Token.objects.bulk_create(token_store, batch_size=1000)
    logging.info("("+transcript.filename+") Token, utterance bulk calls completed in "+str(round(time.time() - t1, 3))+' seconds')

def flatten_list(hierarchical_list, list_name = None):    
    # list_name is for debugging
    if list_name is not None:
        logging.debug('Flattening '+list_name+' ('+str(len(list_name))+' objects)...')
        logging.debug('Example record:')
        logging.debug(hierarchical_list)

    return([item for sublist in hierarchical_list for item in sublist if item is not None])

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
    for number, unit in re.findall(r'(?P<number>\d+)(?P<period>M|D|Y)', (age or '').split('T')[0]):
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

def prettify(ET, fname):
    # Use for debugging, prettify XML when in PDB 
    xmlstr = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")
    with open(fname, "w") as f:
        f.write(xmlstr)

