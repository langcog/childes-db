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
    return num_morphemes



