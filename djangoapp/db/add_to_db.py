from models import Transcript, Participant, Utterance, Token, Corpus

def migrate():
    from childes import CHILDESCorpusReader

    corpus_root =  '/Users/alessandro/Downloads/'
    corpus_name = 'Sachs-xml/.*.xml'

    corpus = CHILDESCorpusReader(corpus_root, corpus_name)

    corpus_obj = Corpus.objects.get(pk=1)

    for fileid in corpus.fileids():

        print fileid

        # transcript info
        t = Transcript(filename=fileid, corpus=corpus_obj)
        corpus_data = corpus.corpus(fileid)
        for key, val in corpus_data[0].iteritems():
            if key == 'Lang':
                t.languages = val
            elif key == 'Date':
                t.date = val
            elif key == 'Comment':
                t.comment = val
        t.save()


        # participant info
        participants = corpus.participants(fileid)[0]

        for key, val in participants.iteritems():

            part = Participant(code=key, corpus=corpus_obj, transcript=t)
            part.name = val.get('name')
            part.role = val.get('role')
            age = val.get('age')
            if age:
                arr = []
                tmp = ''
                for ch in age[1:]:
                    if ch.isdigit():
                        tmp += ch
                    else:
                        arr.append(int(tmp))
                        tmp = ''

                part.age = (arr[0] * 365) + (arr[1] * 30) + (arr[2])
            part.language = val.get('language')
            part.group = val.get('group')
            part.gender = val.get('gender')
            part.ses = val.get('ses')
            part.education = val.get('education')
            part.custom = val.get('custom')

            part.save()

        # utterance and token info

        for speaker in participants.keys():
            raw_words = corpus.tagged_words(speaker=speaker, relation=True) # do same for replace words
            # stem_words = corpus.tagged_words(speaker=speaker, stem=True, relation=True) # actually utts..
            # replace_words = corpus.tagged_words(speaker=speaker, replace=True)

            speaker_obj = Participant.objects.get(transcript=t, code=speaker)
            for i, utt_arr in enumerate(raw_words):
                utt = Utterance(speaker=speaker_obj, transcript=t)
                utt.save()
                # stem_tokens = stem_words[i]
                # replace_tokens = replace_words[i]
                for ind, word_tuple in enumerate(utt_arr):
                    token = Token(gloss=word_tuple[0])
                    if len(word_tuple) == 2:
                        token.part_of_speech = word_tuple[1]
                    if len(word_tuple) == 3:
                        token.relation = word_tuple[2]

                    # token.stem = stem_tokens[ind][0]
                    # token.replacement = replace_tokens[ind][0]

                    token.utterance = utt
                    token.speaker = speaker_obj
                    token.save()












