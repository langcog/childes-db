from db.childes import CHILDESCorpusReader
import pdb

#Script for manual "unit testing"
xml_dir = '/shared_hd1/childes-db-xml/Eng-NA/Providence/Alex/'

test_reader = CHILDESCorpusReader(xml_dir, '.*.xml')
target_trns = '010726.xml'
fids = test_reader.fileids()
#fid = fids.indexof(target_trns)
sents = test_reader.get_custom_sents(target_trns)
for sent in sents:
    utt_gloss = []
    for token in sent['tokens']:
        # TODO use null or blank?
        gloss = token.get('gloss', '')
        utt_gloss.append(gloss)
    # TODO use map instead of tuple
#words = test_reader.words(fileids = [fid])
pdb.set_trace()