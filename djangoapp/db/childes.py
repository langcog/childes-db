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

        #Returns zero if the list has all empty strings or lists
        morpheme_length = compute_morpheme_length([prefixes, stem, suffixes, clitic])
        return prefix, pos, stem, suffix, english_translation, clitic, morpheme_length if morpheme_length > 0 else None



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

        results2 = []
        for xmlsent in xmldoc.findall('.//{%s}u' % NS):

            # TODO confusing tuple structure, use map
            utt = {}

            utt = ()

            sentID = xmlsent.get('uID')
            sents = []
            # place this in map
            speaker = xmlsent.get('who') # ME

            utt['sent_id'] = sentID
            utt['speaker'] = speaker

            #utt += (sentID, speaker)

            tokens = []

            token_order = 0

            skip_replacement_counter = 0

            # extract utterance terminator
            terminator = xmlsent.find(".//{%s}t" % NS).attrib['type']
            utt['term'] = terminator
            #utt += (terminator,)

            # get dependent tiers / annotations
            # TODO get a bunch of stuff and return in convenient format
            annotations = []
            annotation_elements = xmlsent.findall(".//{%s}a" % NS)
            for element in annotation_elements:
                annotation = {}
                annotation['type'] = element.attrib.get('type')
                annotation['flavor'] = element.attrib.get('flavor')
                annotation['who'] = element.attrib.get('who')
                annotation['text'] = element.text
                annotations.append(annotation)

            #utt += (annotations,)
            utt['annotations'] = annotations
            # does this capture the phonetic tier?

            # extract media info, if it exists
            media = {}
            media_element = xmlsent.findall(".//{%s}media" % NS)

            if media_element:
                media['start'] = media_element[0].attrib['start']
                media['end'] = media_element[0].attrib['end']
                media['unit'] = media_element[0].attrib['unit']

            #utt += (media,)
            utt['media'] = media


            # Pull out the phonology tiers
            if fileHasPhonology:
                actual_pho, model_pho = get_phonology(xmlsent, speaker, sentID, fileid)
                num_tokens = len(xmlsent.findall('.//{%s}w' % NS))
                include_actual_pho = num_tokens == len(actual_pho)
                include_model_pho = num_tokens == len(model_pho)
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

                token = {}

                if xmlword.get('type') == 'omission':                    
                    continue

                suffixStem = None

                #xstr = lambda s: "" if s is None else unicode(s)                
                xstr = lambda s: "" if s is None else s

                if xmlword.find('.//{%s}langs' % (NS)):
                    xmlword.text = xmlword.find('.//{%s}langs' % (NS)).tail

                # handles compounds and ignores shortenings (?)
                text_tags = ["{%s}wk" % NS, "{%s}p" % NS, "{%s}shortening" % NS]
                if xmlword.findall('*'):
                    word_tags = xmlword.findall('*')
                    text = xstr(xmlword.text)
                    for word_tag in word_tags:
                        if word_tag.tag in text_tags:
                            if word_tag.tag == "{%s}wk" % NS:
                                text += "+"
                            text += xstr(word_tag.text) + xstr(word_tag.tail)
                    xmlword.text = text

                if xmlword.text:
                    word = xmlword.text
                    token['gloss'] = xmlword.text.strip()
                else:
                    print('empty word in sentence '+ str(sentID))
                    word = ''
                    token['gloss'] = ''    

                # check if this is a replacement, and then build rep, stem, etc from children
                if xmlword.find('.//{%s}replacement' % (NS)):
                    # save children in replacement field
                    # iterate over children
                    replacements = []
                    prefix = []
                    pos = []
                    stems = []
                    suffix = []
                    english = []
                    clitics = []
                    relations = []
                    morpheme_length = None
                    children = xmlword.findall('.//{%s}w' % NS)
                    for child in children:
                        if child.text:
                            replacements.append(child.text)

                        prefix_result, pos_result, stem_result, suffix_result, english_result, clitic_result, morpheme_length_result = \
                            self._get_morphology(child)

                        if prefix_result:
                            prefix.append(prefix_result)

                        # pos_result = self._get_pos(child, None)
                        if pos_result:
                            pos.append(pos_result)

                        # stem_result = self._get_stem(child)
                        if stem_result:
                            stems.append(stem_result)

                        if suffix_result:
                            suffix.append(suffix_result)

                        if english_result:
                            english.append(english_result)

                        if clitic_result:
                            clitics.append(clitic_result)

                        relation_result = self._get_relation(child)
                        if relation_result:
                            relations.append(relation_result)

                        if morpheme_length_result:
                            if morpheme_length:
                                morpheme_length += morpheme_length_result
                            else:
                                morpheme_length = morpheme_length_result

                    token['replacement'] = ' '.join(replacements)
                    token['prefix'] = ' '.join(prefix)
                    token['pos'] = ' '.join(pos)
                    token['stem'] = ' '.join(stems)
                    token['suffix'] = ' '.join(suffix)
                    token['english'] = ' '.join(english)
                    token['clitic'] = ' '.join(clitics)
                    token['relation'] = ' '.join(relations)
                    token['morpheme_length'] = morpheme_length

                    skip_replacement_counter = len(children)
                else: # else get stem and pos for this word
                    # word = word.strip()

                    token['prefix'], token['pos'], token['stem'], token['suffix'], token['english'], token['clitic'], token['morpheme_length'] = \
                        self._get_morphology(xmlword)

                    # token['stem'] = self._get_stem(xmlword)  # if suffix, should be in same column
                    # token['pos'] = self._get_pos(xmlword, suffixStem)
                    token['relation'] = self._get_relation(xmlword)



                    # replacement_elems = filter(lambda x: x.tag == '{%s}w' % NS, [e for e in xmlword.iter() if e is not xmlword])
                    # replacements = [r.text for r in replacement_elems]
                    # replacement_str = ' '.join(replacements)
                    # if replacement_str:
                    #     token['replacement'] = replacement_str
                    #     skip_replacement_counter = len(replacements)
                # parent_map = dict((c, p) for p in tree.getiterator() for c in p)
                #
                # if parent_map.get(xmlword) and parent_map.get(xmlword).tag == '{%s}replacement' % NS:
                #     last_token = tokens[len(tokens) - 1]
                #     last_token['replacement'] = token['gloss']
                #     continue # don't save this token in tokens array

                        # strip tailing space
                token_order += 1
                token['order'] = token_order

                # only include the phonetic information at the word level if it aligns with the set of words
                if fileHasPhonology:
                    if include_actual_pho:
                        token['pho'] = actual_pho[(token_order -1)]
                    else:
                        # mismatch in actual_pho and utterance length; not including actual pho at the word level
                        token['pho'] = ''
                        
                    if include_model_pho:
                        token['mod'] = model_pho[(token_order -1)]
                    else: 
                        # mismatch in model_pho and utterance length; not including model pho at the word level
                        token['mod'] = ''
                else:
                    # whole file does not have phonology
                    token['pho'] = ''
                    token['mod'] = ''

                tokens.append(token)
                # if suffixStem:
                #     sents.append(suffixStem)
            utt['tokens'] = tokens
            results2.append(utt)
            #results2.append(utt + (tokens,) + (actual_pho,) + (model_pho,))
        return results2

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
                    xstr = lambda s: "" if s is None else unicode(s)
                    if replace and xmlword.find('.//{%s}replacement' % (NS)):
                        continue

                    if xmlword.find('.//{%s}langs' % (NS)):
                        xmlword.text = xmlword.find('.//{%s}langs' % (NS)).tail

                    text_tags = ["{%s}wk" % NS, "{%s}p" % NS, "{%s}shortening" % NS]
                    if xmlword.findall('*'):
                        word_tags = xmlword.findall('*')
                        text = xstr(xmlword.text)
                        for word_tag in word_tags:
                            if word_tag.tag in text_tags:
                                if word_tag.tag == "{%s}wk" % NS:
                                    text += "+"
                                text += xstr(word_tag.text) + xstr(word_tag.tail)
                        xmlword.text = text

                    if xmlword.text:
                        word = xmlword.text
                    else:
                        print('empty word in sentence '+str(sentID))
                        word = ''

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
