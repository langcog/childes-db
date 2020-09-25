#!/usr/bin/env python
# CHILDES XML Corpus Reader

# Copyright (C) 2001-2012 NLTK Project
# Author: Tomonori Nagano <tnagano@gc.cuny.edu>
#         Alexis Dimitriadis <A.Dimitriadis@uu.nl>
# URL: <http://www.nltk.org/>
# For license information, see LICENSE.TXT

"""
Corpus reader for the XML version of the CHILDES corpus.
"""
__docformat__ = 'epytext en'

import re   
from collections import defaultdict
import warnings
warnings.filterwarnings("ignore", message="numpy.dtype size changed")
warnings.filterwarnings("ignore", message="numpy.ufunc size changed")
#warnings.warn = lambda *a, **kw: False
import copy

from nltk.util import flatten
from nltk.corpus.reader.util import concat
from nltk.corpus.reader.xmldocs import XMLCorpusReader, ElementTree
from db.reader_utils import *
import pdb

# to resolve the namespace issue
NS = 'http://www.talkbank.org/ns/talkbank'

from xml.dom import minidom

class CHILDESCorpusReader(XMLCorpusReader):
    """
    Corpus reader for the XML version of the CHILDES corpus.
    The CHILDES corpus is available at ``http://childes.psy.cmu.edu/``. The XML
    version of CHILDES is located at ``http://childes.psy.cmu.edu/data-xml/``.
    Copy the needed parts of the CHILDES XML corpus into the NLTK data directory
    (``nltk_data/corpora/CHILDES/``).

    For access to the file text use the usual nltk functions,
    ``words()``, ``sents()``, ``tagged_words()`` and ``tagged_sents()``.
    """
    def __init__(self, root, fileids, lazy=True):
        XMLCorpusReader.__init__(self, root, fileids)
        self._lazy = lazy

    def words(self, fileids=None, speaker='ALL', stem=False,
            relation=False, strip_space=True, replace=False):
        """
        :return: the given file(s) as a list of words
        :rtype: list(str)

        :param speaker: If specified, select specific speaker(s) defined
            in the corpus. Default is 'ALL' (all participants). Common choices
            are 'CHI' (the child), 'MOT' (mother), ['CHI','MOT'] (exclude
            researchers)
        :param stem: If true, then use word stems instead of word strings.
        :param relation: If true, then return tuples of (stem, index,
            dependent_index)
        :param strip_space: If true, then strip trailing spaces from word
            tokens. Otherwise, leave the spaces on the tokens.
        :param replace: If true, then use the replaced (intended) word instead
            of the original word (e.g., 'wat' will be replaced with 'watch')
        """
        sent=None
        pos=False
        return concat([self._get_words(fileid, speaker, sent, stem, relation,
            pos, strip_space, replace) for fileid in self.abspaths(fileids)])

    def tagged_words(self, fileids=None, speaker='ALL', stem=False,
            relation=False, strip_space=True, replace=False):
        """
        :return: the given file(s) as a list of tagged
            words and punctuation symbols, encoded as tuples
            ``(word,tag)``.
        :rtype: list(tuple(str,str))

        :param speaker: If specified, select specific speaker(s) defined
            in the corpus. Default is 'ALL' (all participants). Common choices
            are 'CHI' (the child), 'MOT' (mother), ['CHI','MOT'] (exclude
            researchers)
        :param stem: If true, then use word stems instead of word strings.
        :param relation: If true, then return tuples of (stem, index,
            dependent_index)
        :param strip_space: If true, then strip trailing spaces from word
            tokens. Otherwise, leave the spaces on the tokens.
        :param replace: If true, then use the replaced (intended) word instead
            of the original word (e.g., 'wat' will be replaced with 'watch')
        """
        sent=None
        pos=True
        return concat([self._get_words(fileid, speaker, sent, stem, relation,
            pos, strip_space, replace) for fileid in self.abspaths(fileids)])

    def sents(self, fileids=None, speaker='ALL', stem=False,
            relation=None, strip_space=True, replace=False):
        """
        :return: the given file(s) as a list of sentences or utterances, each
            encoded as a list of word strings.
        :rtype: list(list(str))

        :param speaker: If specified, select specific speaker(s) defined
            in the corpus. Default is 'ALL' (all participants). Common choices
            are 'CHI' (the child), 'MOT' (mother), ['CHI','MOT'] (exclude
            researchers)
        :param stem: If true, then use word stems instead of word strings.
        :param relation: If true, then return tuples of ``(str,pos,relation_list)``.
            If there is manually-annotated relation info, it will return
            tuples of ``(str,pos,test_relation_list,str,pos,gold_relation_list)``
        :param strip_space: If true, then strip trailing spaces from word
            tokens. Otherwise, leave the spaces on the tokens.
        :param replace: If true, then use the replaced (intended) word instead
            of the original word (e.g., 'wat' will be replaced with 'watch')
        """
        sent=True
        pos=False
        return concat([self._get_words(fileid, speaker, sent, stem, relation,
            pos, strip_space, replace) for fileid in self.abspaths(fileids)])

    def tagged_sents(self, fileids=None, speaker='ALL', stem=False,
            relation=None, strip_space=True, replace=False):
        """
        :return: the given file(s) as a list of
            sentences, each encoded as a list of ``(word,tag)`` tuples.
        :rtype: list(list(tuple(str,str)))

        :param speaker: If specified, select specific speaker(s) defined
            in the corpus. Default is 'ALL' (all participants). Common choices
            are 'CHI' (the child), 'MOT' (mother), ['CHI','MOT'] (exclude
            researchers)
        :param stem: If true, then use word stems instead of word strings.
        :param relation: If true, then return tuples of ``(str,pos,relation_list)``.
            If there is manually-annotated relation info, it will return
            tuples of ``(str,pos,test_relation_list,str,pos,gold_relation_list)``
        :param strip_space: If true, then strip trailing spaces from word
            tokens. Otherwise, leave the spaces on the tokens.
        :param replace: If true, then use the replaced (intended) word instead
            of the original word (e.g., 'wat' will be replaced with 'watch')
        """
        sent=True
        pos=True
        return concat([self._get_words(fileid, speaker, sent, stem, relation,
            pos, strip_space, replace) for fileid in self.abspaths(fileids)])

    def corpus(self, fileids=None):
        """
        :return: the given file(s) as a dict of ``(corpus_property_key, value)``
        :rtype: list(dict)
        """
        return [self._get_corpus(fileid) for fileid in self.abspaths(fileids)]

    def _get_corpus(self, fileid):
        results = dict()
        xmldoc = ElementTree.parse(fileid).getroot()
        for key, value in xmldoc.items():
            results[key] = value
        return results

    def participants(self, fileids=None):
        """
        :return: the given file(s) as a dict of
            ``(participant_property_key, value)``
        :rtype: list(dict)
        """
        return [self._get_participants(fileid)
                            for fileid in self.abspaths(fileids)]

    def _get_participants(self, fileid):
        # multidimensional dicts
        def dictOfDicts():
            return defaultdict(dictOfDicts)

        xmldoc = ElementTree.parse(fileid).getroot()
        # getting participants' data
        pat = dictOfDicts()
        for participant in xmldoc.findall('.//{%s}Participants/{%s}participant'
                                          % (NS,NS)):
            for (key,value) in participant.items():
                pat[participant.get('id')][key] = value
        return pat

    def age(self, fileids=None, speaker='CHI', month=False):
        """
        :return: the given file(s) as string or int
        :rtype: list or int

        :param month: If true, return months instead of year-month-date
        """
        return [self._get_age(fileid, speaker, month)
                for fileid in self.abspaths(fileids)]

    def _get_age(self, fileid, speaker, month):
        xmldoc = ElementTree.parse(fileid).getroot()
        for pat in xmldoc.findall('.//{%s}Participants/{%s}participant'
                                  % (NS,NS)):
            try:
                if pat.get('id') == speaker:
                    age = pat.get('age')
                    if month:
                        age = self.convert_age(age)
                    return(age)
            # some files don't have age data
            except:
                return(None)

    def sex(self, fileids=None, speaker='CHI'):
        """
        :return: the given file(s) as string or int
        :rtype: list or int

        :param month: If true, return months instead of year-month-date
        """
        return [self._get_sex(fileid, speaker)
                for fileid in self.abspaths(fileids)]

    def _get_sex(self, fileid, speaker):
        xmldoc = ElementTree.parse(fileid).getroot()
        for pat in xmldoc.findall('.//{%s}Participants/{%s}participant'
                                  % (NS,NS)):
            try:
                if pat.get('id') == speaker:
                    sex = pat.get('sex')
                    return sex
            # some files don't have age data
            except:
                return None

    def convert_age(self, age_year):
        "Caclculate age in months from a string in CHILDES format"
        m = re.match("P(\d+)Y(\d+)M?(\d?\d?)D?",age_year)
        age_month = int(m.group(1))*12 + int(m.group(2))
        try:
            if int(m.group(3)) > 15:
                age_month += 1
        # some corpora don't have age information?
        except:
            pass
        return age_month

    def MLU(self, fileids=None, speaker='CHI'):
        """
        :return: the given file(s) as a floating number
        :rtype: list(float)
        """
        return [self._getMLU(fileid, speaker=speaker)
                for fileid in self.abspaths(fileids)]

    def _getMLU(self, fileid, speaker):
        sents = self._get_words(fileid, speaker=speaker, sent=True, stem=True,
                    relation=False, pos=True, strip_space=True, replace=True)

        results, lastSent, numFillers, sentDiscount = mlu_calc_components(sents)

        try:
            thisWordList = flatten(results)
            # count number of morphemes
            # (e.g., 'read' = 1 morpheme but 'read-PAST' is 2 morphemes)
            numWords = float(len(flatten([word.split('-')
                                          for word in thisWordList]))) - numFillers
            numSents = float(len(results)) - sentDiscount
            mlu = numWords/numSents
        except ZeroDivisionError:
            mlu = 0
        # return {'mlu':mlu,'wordNum':numWords,'sentNum':numSents}
        return mlu

    def _get_relation(self, xmlword):
        # relational
        # the gold standard is stored in
        # <mor></mor><mor type="trn"><gra type="grt">
        # original: if relation == True:        

        relation = ''
        for xmlstem_rel in xmlword.findall('.//{%s}mor/{%s}gra' % (NS, NS)):
            if not xmlstem_rel.get('type') == 'grt':
                # word = (word[0], word[1],
                #         xmlstem_rel.get('index')
                #         + "|" + xmlstem_rel.get('head')
                #         + "|" + xmlstem_rel.get('relation'))

                # store relation in token map
                relation = xmlstem_rel.get('index') + "|" + xmlstem_rel.get('head') + "|" + xmlstem_rel.get('relation')

                # ignore gold standard for now
                # else:
                #     word = (word[0], word[1], word[2],
                #             word[0], word[1],
                #             xmlstem_rel.get('index')
                #             + "|" + xmlstem_rel.get('head')
                #             + "|" + xmlstem_rel.get('relation'))
        # try:  # what is this?
        #     for xmlpost_rel in xmlword.findall('.//{%s}mor/{%s}mor-post/{%s}gra'
        #                                                % (NS, NS, NS)):
        #         if not xmlpost_rel.get('type') == 'grt':
        #             # suffixStem = (suffixStem[0],
        #             #               suffixStem[1],
        #             #               xmlpost_rel.get('index')
        #             #               + "|" + xmlpost_rel.get('head')
        #             #               + "|" + xmlpost_rel.get('relation'))

        #             # add suffix relation to normal relation
        #             relation += ' ' + xmlpost_rel.get('index') \
        #                                  + "|" + xmlpost_rel.get('head') \
        #                                  + "|" + xmlpost_rel.get('relation')
        #             # else:
        #             #     suffixStem = (suffixStem[0], suffixStem[1],
        #             #                   suffixStem[2], suffixStem[0],
        #             #                   suffixStem[1],
        #             #                   xmlpost_rel.get('index')
        #             #                   + "|" + xmlpost_rel.get('head')
        #             #                   + "|" + xmlpost_rel.get('relation'))
        # except:
        #     pass

        return relation

    def _get_pos(self, xmlword, suffixStem):
        # pos
        # original if relation or pos:
        pos = ''
        try:
            xmlpos = xmlword.findall(".//{%s}c" % NS)
            # word = (word, xmlpos[0].text)
            # add pos to map
            pos = xmlpos[0].text
            if len(xmlpos) != 1 and suffixStem:
                suffixStem = (suffixStem, xmlpos[1].text)
                pos += ' ' + xmlpos[1].text  # POS of suffix
        except:
            pass
            # we don't really do anyting with below vars...
            # word = (word, None)
            # if suffixStem:
            #     suffixStem = (suffixStem, None)
        return pos

    def _get_morphology(self, xmlword):
        NS = 'http://www.talkbank.org/ns/talkbank'

        #Calling functions from reader_utils
        prefixes = get_list_morphemes('.//{%s}mor/{%s}mw/{%s}mpfx' % (NS, NS, NS), xmlword)
        prefix = ' '.join(prefixes)

        pos = get_single_morpheme('.//{%s}mor/{%s}mw/{%s}pos/{%s}c' % (NS, NS, NS, NS), xmlword)

        stem = get_single_morpheme('.//{%s}mor/{%s}mw/{%s}stem' % (NS, NS, NS), xmlword)

        suffixes = get_list_morphemes('.//{%s}mor/{%s}mw/{%s}mk' % (NS, NS, NS), xmlword)
        suffix = " ".join(suffixes)

        english_translation = get_single_morpheme('.//{%s}mor/{%s}menx' % (NS, NS), xmlword)
        clitic = get_single_morpheme('.//{%s}mor/{%s}mor-post' % (NS, NS), xmlword)

        morpheme_length = compute_morpheme_length([prefixes, stem, suffixes, clitic])
        return {'prefix': prefix, 'pos': pos, 'stem': stem, 'english': english_translation, 'clitic': clitic,
            'morpheme_length': morpheme_length}

    def _get_stem(self, xmlword):
        # stem
        stem = ''
        # original if relation or stem
        try:
            xmlstem = xmlword.find('.//{%s}stem' % NS)
            # word = xmlstem.text
            # replaces word with stem, instead add to map
            stem = xmlstem.text
        except:
            pass
        # if there is an inflection
        try:
            xmlinfl = xmlword.find('.//{%s}mor/{%s}mw/{%s}mk'
                                   % (NS, NS, NS))
            # word += '-' + xmlinfl.text
            stem += '-' + xmlinfl.text
        except:
            pass
        # if there is a suffix
        try:
            xmlsuffix = xmlword.find('.//{%s}mor/{%s}mor-post/{%s}mw/{%s}stem'
                                     % (NS, NS, NS, NS))
            suffixStem = xmlsuffix.text
            stem += ' ' + suffixStem
        except AttributeError:
            suffixStem = ""
        return stem

    def get_custom_sents(self, fileid):  # speaker, sent, stem, relation, pos, strip_space, replace):
        fileid = self.abspaths([fileid])[0]
        tree = ElementTree.parse(fileid)
        xmldoc = tree.getroot()

        # check if this file has phonological transcriptions        
        if xmldoc.find('.//{%s}pw' % NS) is not None:
            fileHasPhonology = True
            print('File has phonological transcripts. Processing...')
        else:
            fileHasPhonology = False
            print('File has no phonological transcripts. Skipping extraction of phonological information.')

        processed_sents = []
        for xmlsent in xmldoc.findall('.//{%s}u' % NS):

            # DONE confusing tuple structure, use map
            utt = {}

            sentID = xmlsent.get('uID')
            speaker = xmlsent.get('who')

            utt['sent_id'] = sentID
            utt['speaker'] = speaker

            tokens = []
            token_order = 0
            skip_replacement_counter = 0

            # extract utterance terminator
            terminator = xmlsent.find(".//{%s}t" % NS).attrib['type']
            utt['term'] = terminator

            # get dependent tiers / annotations
            # TODO get a bunch of stuff and return in convenient format
            utt['annotations'] = get_annotations(xmlsent)

            # extract media info, if it exists
            utt['media'] = get_media_info(xmlsent)
            token_phon_criteria = {} 
            #Putting the booleans and transcriptions here for phonetic token extraction (see get_token_phonology in reader_utils)

            if fileHasPhonology:
                        # Pull out the phonology tiers
                actual_pho, model_pho = get_phonology(xmlsent, speaker, sentID, fileid)
                num_tokens = len(xmlsent.findall('.//{%s}w' % NS))
                include_actual_pho = num_tokens == len(actual_pho)
                include_model_pho = num_tokens == len(model_pho)
                token_phon_criteria = {'actual': {'include': include_actual_pho, 'phons': actual_pho},
                        'model': {'include': include_model_pho, 'phons': model_pho}}

            else:
                actual_pho = []
                model_pho = []

            utt['actual_pho'] = actual_pho
            utt['model_pho'] = model_pho

            for xmlword in xmlsent.findall('.//{%s}w' % NS):

                # skip the replacements of a word - they've already been considered
                if skip_replacement_counter > 0:
                    skip_replacement_counter -= 1
                    continue
                token, skip_replacement_counter = self.get_token_for_utterance(xmlword, skip_replacement_counter, 
                sentID, fileHasPhonology, token_phon_criteria, token_order)
                if token:
                    tokens.append(token)
                # if suffixStem:
                #     sents.append(suffixStem)
            utt['tokens'] = tokens
            processed_sents.append(utt)
        return processed_sents

    def get_token_for_utterance(self, xmlword, skip_replacement_counter,
     sentID, fileHasPhonology, phon_criteria, token_order):
     #Keeping the token populating code in a separate function 
        if xmlword.get('type') == 'omission':                    
            return None, skip_replacement_counter
        
        token = {}
        #xstr = lambda s: "" if s is None else unicode(s)
        token['gloss'] = extract_gloss(xmlword, sentID)                

        # check if this is a replacement, and then build rep, stem, etc from children
        if xmlword.find('.//{%s}replacement' % (NS)):
            # save children in replacement field
            # iterate over children
            replacements, relations, morphology, children_length = self.replacement_token_data(xmlword) 
            token['replacement'] = ' '.join(replacements)
            token['relation'] = ' '.join(relations)

            for k in morphology.keys():
                if k != 'morpheme_length':
                    token[k] = ' '.join(morphology[k])
            token['morpheme_length'] = morphology['morpheme_length']

            skip_replacement_counter = children_length
        else: # else get stem and pos for this word
            # word = word.strip()
            morph_dict = self._get_morphology(xmlword)
            token.update(morph_dict)
            # token['stem'] = self._get_stem(xmlword)  # if suffix, should be in same column
            # token['pos'] = self._get_pos(xmlword, suffixStem)
            token['relation'] = self._get_relation(xmlword)
        token_order += 1
        token['order'] = token_order

        token = get_token_phonology(token, fileHasPhonology, phon_criteria, token_order)
        return token, skip_replacement_counter

    def replacement_token_data(self, xmlword):
        """
        If xmlword has replacements, iterates through all the children of the token 
        and gets the following attributes: morphology (prefix, suffix, PoS, stem, English translation, clitic,
        morpheme length), replacement text, and dependency relations.
        Also outputs the number children such that 
        """
        replacements = []
        relations = []

        global_morphology = {
            'prefix' : [],
            'pos': [],
            'stem': [],
            'suffix': [],
            'english': [],
            'clitic': [],
            'morpheme_length': None
        }
        children = xmlword.findall('.//{%s}w' % NS)
        for child in children:
            if child.text:
                replacements.append(child.text)

            child_morphology = self._get_morphology(child)

            for key in child_morphology.keys():
                if child_morphology[key]:
                    if key == 'morpheme_length':
                        if child_morphology['morpheme_length'] != None:
                            if global_morphology['morpheme_length'] == None:
                                global_morphology['morpheme_length'] = 0
                            global_morphology[key] += child_morphology['morpheme_length']
                    else:
                        value = child_morphology[key]
                        #FIXME Can we do global_morphology[key].append(value)?
                        prev_global_value = global_morphology[key]
                        prev_global_value.append(value)
                        global_morphology[key] = prev_global_value

            relation_result = self._get_relation(child)
            if relation_result:
                relations.append(relation_result)

        return replacements, relations, global_morphology, len(children)

    def _get_words(self, fileid, speaker, sent, stem, relation, pos,
            strip_space, replace):
        if isinstance(speaker, str) and speaker != 'ALL':  # ensure we have a list of speakers
            speaker = [ speaker ]
        xmldoc = ElementTree.parse(fileid).getroot()
        # processing each xml doc
        results = []
        for xmlsent in xmldoc.findall('.//{%s}u' % NS):
            sentID  = xmlsent.get('uID')
            sents = []
            # select speakers
            if speaker == 'ALL' or xmlsent.get('who') in speaker:
                for xmlword in xmlsent.findall('.//{%s}w' % NS):

                    if xmlword.get('type') == 'omission':                        
                        # is this a 0-marked token?
                        continue

                    infl = None ; suffixStem = None

                    # getting replaced words
                    word = extract_gloss(xmlword, sentID)
                    # strip tailing space
                    if strip_space:
                        word = word.strip()

                    # stem
                    if relation or stem:
                        try:
                            xmlstem = xmlword.find('.//{%s}stem' % NS)
                            word = xmlstem.text
                        except:
                            pass
                        # if there is an inflection
                        try:
                            xmlinfl = xmlword.find('.//{%s}mor/{%s}mw/{%s}mk'
                                                   % (NS,NS,NS))
                            word += '-' + xmlinfl.text
                        except:
                            pass
                        # if there is a suffix
                        try:
                            xmlsuffix = xmlword.find('.//{%s}mor/{%s}mor-post/{%s}mw/{%s}stem'
                                                     % (NS,NS,NS,NS))
                            suffixStem = xmlsuffix.text
                        except AttributeError:
                            suffixStem = ""
                    # pos
                    if relation or pos:
                        try:
                            xmlpos = xmlword.findall(".//{%s}c" % NS)
                            word = (word,xmlpos[0].text)
                            if len(xmlpos) != 1 and suffixStem:
                                suffixStem = (suffixStem,xmlpos[1].text)
                        except:
                            word = (word,None)
                            if suffixStem:
                                suffixStem = (suffixStem,None)
                    # relational
                    # the gold standard is stored in
                    # <mor></mor><mor type="trn"><gra type="grt">
                    if relation == True:
                        for xmlstem_rel in xmlword.findall('.//{%s}mor/{%s}gra'
                                                           % (NS,NS)):
                            if not xmlstem_rel.get('type') == 'grt':
                                word = (word[0], word[1],
                                        xmlstem_rel.get('index')
                                        + "|" + xmlstem_rel.get('head')
                                        + "|" + xmlstem_rel.get('relation'))
                            else:
                                word = (word[0], word[1], word[2],
                                        word[0], word[1],
                                        xmlstem_rel.get('index')
                                        + "|" + xmlstem_rel.get('head')
                                        + "|" + xmlstem_rel.get('relation'))
                        try:
                            for xmlpost_rel in xmlword.findall('.//{%s}mor/{%s}mor-post/{%s}gra'
                                                               % (NS,NS,NS)):
                                if not xmlpost_rel.get('type') == 'grt':
                                    suffixStem = (suffixStem[0],
                                                  suffixStem[1],
                                                  xmlpost_rel.get('index')
                                                  + "|" + xmlpost_rel.get('head')
                                                  + "|" + xmlpost_rel.get('relation'))
                                else:
                                    suffixStem = (suffixStem[0], suffixStem[1],
                                                  suffixStem[2], suffixStem[0],
                                                  suffixStem[1],
                                                  xmlpost_rel.get('index')
                                                  + "|" + xmlpost_rel.get('head')
                                                  + "|" + xmlpost_rel.get('relation'))
                        except:
                            pass                    
                    sents.append(word)
                    if suffixStem:
                        sents.append(suffixStem)
                if sent or relation:
                    results.append(sents)
                else:
                    results.extend(sents)
        return results


    # Ready-to-use browser opener

    """
    The base URL for viewing files on the childes website. This
    shouldn't need to be changed, unless CHILDES changes the configuration
    of their server or unless the user sets up their own corpus webserver.
    """
    childes_url_base = r'http://childes.psy.cmu.edu/browser/index.php?url='


    def webview_file(self, fileid, urlbase=None):
        """Map a corpus file to its web version on the CHILDES website,
        and open it in a web browser.

        The complete URL to be used is:
            childes.childes_url_base + urlbase + fileid.replace('.xml', '.cha')

        If no urlbase is passed, we try to calculate it.  This
        requires that the childes corpus was set up to mirror the
        folder hierarchy under childes.psy.cmu.edu/data-xml/, e.g.:
        nltk_data/corpora/childes/Eng-USA/Cornell/??? or
        nltk_data/corpora/childes/Romance/Spanish/Aguirre/???

        The function first looks (as a special case) if "Eng-USA" is
        on the path consisting of <corpus root>+fileid; then if
        "childes", possibly followed by "data-xml", appears. If neither
        one is found, we use the unmodified fileid and hope for the best.
        If this is not right, specify urlbase explicitly, e.g., if the
        corpus root points to the Cornell folder, urlbase='Eng-USA/Cornell'.
        """

        import webbrowser, re

        if urlbase:
            path = urlbase+"/"+fileid
        else:
            full = self.root + "/" + fileid
            full = re.sub(r'\\', '/', full)
            if '/childes/' in full.lower():
                # Discard /data-xml/ if present
                path = re.findall(r'(?i)/childes(?:/data-xml)?/(.*)\.xml', full)[0]
            elif 'eng-usa' in full.lower():
                path = 'Eng-USA/' + re.findall(r'/(?i)Eng-USA/(.*)\.xml', full)[0]
            else:
                path = fileid

        # Strip ".xml" and add ".cha", as necessary:
        if path.endswith('.xml'):
            path = path[:-4]

        if not path.endswith('.cha'):
            path = path+'.cha'

        url = self.childes_url_base + path

        webbrowser.open_new_tab(url)
        print("Opening in browser: "+url)
        # Pausing is a good idea, but it's up to the user...
        # raw_input("Hit Return to continue")

def get_phonology(xmlsent, speaker_code, sentID, fileid):

    actual_pho = [] #initial value
    model_pho = [] #initial value

    actual_words = xmlsent.findall('.//{%s}pg/{%s}actual/{%s}pw' % (NS, NS, NS))
    model_words = xmlsent.findall('.//{%s}pg/{%s}model/{%s}pw' % (NS, NS, NS))

    words = [x.text for x in xmlsent.findall('.//{%s}w' % NS)]
    words = [x for x in words if x is not None]

    diagnostic_info = '"'+' '.join(words)+'" ('+fileid+': '+str(sentID)+')'

    if (len(actual_words) > 0) and (speaker_code != 'CHI'):   
        print('Actual phonology tier is populated for a non child speaker! '+diagnostic_info)

    if (len(model_words) > 0) and (speaker_code != 'CHI'):   
        print('Model phonology tier is populated for a non child speaker! '+diagnostic_info)

    # Prep the phonology in preparation to merge back in when tokens are ready
    if (len(actual_words) == 0) and (speaker_code == 'CHI'):
        if len(xmlsent.findall('.//{%s}actual' % NS)) > 0:
            print('Actual pho tier was found in a weird place! '+diagnostic_info)
            import pdb
            pdb.set_trace()
            #[ ] are there instances where phonology is embedded at a different level?
        else:
            
            if not 'xxx' in words: #cut down on logging
                print("No 'actual' phonetic transcript! " + diagnostic_info)

    if (len(model_words) == 0) and (speaker_code == 'CHI'):
        if len(xmlsent.findall('.//{%s}model' % NS)) > 0:
            print('Model pho tier was found in a weird place! '+diagnostic_info)
            import pdb
            pdb.set_trace()
            #[ ] are there instances where phonology is embedded at a different level?
        else:
            
            if not 'xxx' in words: #cut down on logging
                print("No 'model' phonetic transcript! " + diagnostic_info)
            
    if len(actual_words) > 0:
        actual_pho =  [''.join([x.text for x in y.findall('{%s}ph' % NS)]) for y in actual_words]
    
    if len(model_words) > 0:
        model_pho =  [''.join([x.text for x in y.findall('{%s}ph' % NS)]) for y in model_words]        

    return(actual_pho, model_pho)


def demo(corpus_root=None):
    """
    The CHILDES corpus should be manually downloaded and saved
    to ``[NLTK_Data_Dir]/corpora/childes/``
    """
    if not corpus_root:
        from nltk.data import find
        corpus_root = find('corpora/childes/data-xml/Eng-USA/')

    try:
        childes = CHILDESCorpusReader(corpus_root, u'.*.xml')
        # describe all corpus
        for file in childes.fileids()[:5]:
            corpus = ''
            corpus_id = ''
            for (key,value) in childes.corpus(file)[0].items():
                if key == "Corpus": corpus = value
                if key == "Id": corpus_id = value
            #print('Reading '+corpus,corpus_id+' .....')
            # print "words:", childes.words(file)[:7],"..."
            # print "words with replaced words:", childes.words(file, replace=True)[:7]," ..."
            # print "words with pos tags:", childes.tagged_words(file)[:7]," ..."
            # print "words (only MOT):", childes.words(file, speaker='MOT')[:7], "..."
            # print "words (only CHI):", childes.words(file, speaker='CHI')[:7], "..."
            # print "stemmed words:", childes.words(file, stem=True)[:7]," ..."
            # print "words with relations and pos-tag:", childes.words(file, relation=True)[:5]," ..."
            # print "sentence:", childes.sents(file)[:2]," ..."
            # for (participant, values) in childes.participants(file)[0].items():
            #         for (key, value) in values.items():
            #             print "\tparticipant", participant, key, ":", value
            # print "num of sent:", len(childes.sents(file))
            # print "num of morphemes:", len(childes.words(file, stem=True))
            # print "age:", childes.age(file)
            # print "age in month:", childes.age(file, month=True)
            # print "MLU:", childes.MLU(file)
            # print

    except:
        print("""The CHILDES corpus, or the parts you need, should be manually
        downloaded from http://childes.psy.cmu.edu/data-xml/ and saved at
        [NLTK_Data_Dir]/corpora/childes/
            Alternately, you can call the demo with the path to a portion of the CHILDES corpus, e.g.:
        demo('/path/to/childes/data-xml/Eng-USA/")
        """)
        #corpus_root_http = urllib2.urlopen('http://childes.psy.cmu.edu/data-xml/Eng-USA/Bates.zip')
        #corpus_root_http_bates = zipfile.ZipFile(cStringIO.StringIO(corpus_root_http.read()))
        ##this fails
        #childes = CHILDESCorpusReader(corpus_root_http_bates,corpus_root_http_bates.namelist())


if __name__ == "__main__":
    demo()
