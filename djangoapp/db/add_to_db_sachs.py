from models import Transcript, Participant, Utterance, Token, Corpus

def migrate():
    from childes import CHILDESCorpusReader

    corpus_root =  '/Users/alessandro/Downloads/'
    corpus_name = 'Sachs-xml/.*.xml'

    corpus = CHILDESCorpusReader(corpus_root, corpus_name)

    corpus_obj = Corpus.objects.get(pk=1)

    for i, fileid in enumerate(corpus.fileids()):

        if i > 1:
            return

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

        sents = corpus.get_custom_sents(fileid)
        for sent in sents:
            uID = sent[0].replace("u", "")
            speaker = sent[1]
            tokens = sent[2]

            speaker_obj = Participant.objects.get(transcript=t, code=speaker)
            utt = Utterance(speaker=speaker_obj, transcript=t, order=uID)
            utt.save()

            for token in tokens:
                t = Token(
                    gloss=token.get('gloss') or '',
                    replacement=token.get('replacement') or '',
                    stem=token.get('stem') or '',
                    part_of_speech=token.get('pos') or '',
                    relation=token.get('relation') or '',
                    order=token.get('order') or '',
                    speaker=speaker_obj,
                    utterance=utt
                )
                t.save()












