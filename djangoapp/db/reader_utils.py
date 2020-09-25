import pdb
NS = 'http://www.talkbank.org/ns/talkbank'

def mlu_calc_components(sents):    
    results = []
    lastSent = []
    numFillers = 0
    sentDiscount = 0
    for sent in sents:
        posList = [pos for (word,pos) in sent]
        # if any part of the sentence is intelligible
        if any(pos == 'unk' for pos in posList):
            next
        # if the sentence is null
        elif sent == []:
            next
        # if the sentence is the same as the last sent
        elif sent == lastSent:
            next
        else:
            results.append([word for (word,pos) in sent])
            # count number of fillers
            if len(set(['co',None]).intersection(posList)) > 0:
                numFillers += posList.count('co')
                numFillers += posList.count(None)
                sentDiscount += 1
            lastSent = sent
    return results, lastSent, numFillers, sentDiscount

#Helper functions for get_morphology

def get_list_morphemes(query, xmlword):
    """
    Given an XPath (query) and XML object representing a word, returns the list of morphemes specified in the query
    Example use cases: Prefixes & Suffixes
    """
    xml_result = xmlword.findall(query)
    morphemes = []
    if xml_result:
        morphemes = [m.text for m in xml_result]
    return morphemes

def get_single_morpheme(query, xmlword):
    """
    Given an XPath (query) and XML object representing a word, returns the morpheme specified in the query
    Example use cases: Stem & English Translation, with special cases for clitic and PoS
    """
    morpheme = ''
    xml_result = xmlword.findall(query)
    if xml_result:
        if query == './/{%s}mor/{%s}mw/{%s}pos/{%s}c' % (NS, NS, NS, NS): #PoS
            morpheme = xml_result[0].text
            xml_pos_subcategories = xmlword.findall('.//{%s}mor/{%s}mw/{%s}pos/{%s}s' % (NS, NS, NS, NS))
            for xml_pos_subcategory in xml_pos_subcategories:
                morpheme += ":" + xml_pos_subcategory.text
        elif query == './/{%s}mor/{%s}mor-post' % (NS, NS): #clitic
            clitic_parts = xml_result[0].findall('.//{%s}mw' % NS)
            if clitic_parts:
                a = clitic_parts[0].findall('.//{%s}pos/{%s}c' % (NS, NS))
                b = clitic_parts[0].findall('.//{%s}stem' % NS)
                c = clitic_parts[0].findall('.//{%s}mk' % NS)
                morpheme = " ".join([a[0].text if a else "", b[0].text if b else "", c[0].text if c else ""])
        else:
            morpheme = xml_result[0].text
    return morpheme

def compute_morpheme_length(attribs):
    """
    attribs is a list consisting of both strings (stem, clitic) and lists (prefix, suffix)
    Based on whether each object in the list is "True" we increment the number of morphemes
    by 1 (if string) or the length of the list (if list)
    """
    num_morphemes = 0
    for m in attribs:
        if m:
            if type(m) == list:
                num_morphemes += len(m)
            else:
                num_morphemes += 1
    if num_morphemes == 0: #To be consistent with the previous functionality
        return None
    return num_morphemes

#Helper functions for get_custom_sents

def get_annotations(xmlsent):
    """
    TODO figure out this docstring
    """
    annotations = []
    annotation_elements = xmlsent.findall(".//{%s}a" % NS)
    for element in annotation_elements:
        annotation = {}
        annotation['type'] = element.attrib.get('type')
        annotation['flavor'] = element.attrib.get('flavor')
        annotation['who'] = element.attrib.get('who')
        annotation['text'] = element.text
        annot = {'type': element.attrib.get('type'), 'flavor': element.attrib.get('flavor'), 
        'who': element.attrib.get('who'), 'text': element.text}
        annotations.append(annot)
    return annotations

def get_media_info(xmlsent):
    """
    Outputs a dictionary containing information about the audio file corresponding to xmlsent, 
    if it exists
    """
    media = {}
    media_element = xmlsent.findall(".//{%s}media" % NS)

    if media_element:
        media_element = media_element[0]
        media = {'start': media_element.attrib['start'],
                'end': media_element.attrib['end'],
                'unit': media_element.attrib['unit']
        }
    return media

def extract_gloss(xmlword, sentID):
    #TODO rename something better because it is also in the get_words fn
    gloss = ''
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
        #word = xmlword.text
        gloss = xmlword.text.strip()
    else:
        print('empty word in sentence '+ str(sentID))
    return gloss

def get_token_phonology(token, fileHasPhonology, phon_criteria, token_order):
    """
    Refactored this so that it takes in a dictionary with the following structure, otherwise we're
    passing too many parameters into the utterance_tokens instance method 
    phon_criteria = {'actual': {'include': include_actual_pho, 'phons': actual_pho},
                        'model': {'include': include_model_pho, 'phons': model_pho}}
    """
    if fileHasPhonology:
        if phon_criteria['actual']['include']:
            actual_pho = phon_criteria['actual']['phons']
            token['pho'] = actual_pho[(token_order -1)]
        else:
            # mismatch in actual_pho and utterance length; not including actual pho at the word level
            token['pho'] = ''
            
        if phon_criteria['model']['include']:
            model_pho = phon_criteria['actual']['phons']
            token['mod'] = model_pho[(token_order -1)]
        else: 
            # mismatch in model_pho and utterance length; not including model pho at the word level
            token['mod'] = ''
    else:
        # whole file does not have phonology
        token['pho'] = ''
        token['mod'] = ''
    return token
