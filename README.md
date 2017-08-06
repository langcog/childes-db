# childes-db

The CHILDES-db project aims to make [CHILDES](http://childes.talkbank.org/) transcripts more accessible by reducing the amount of preprocessing necessary (e.g., CLAN or specific preprocessing libraries) and by making the individual tokens and utterances available in a tabular format. In addition, we plan to release new dated versions periodically to facilitate replication (the public version of CHILDES currently does not have a versioning system); we are also working on an API (R and/or Pandas) to provide abstractions such that users do not need to write SQL to perform common tasks.

# Schema
### Tables
- `token`: atomic construct, corresponding to a word
- `utterance`: refers to one or more token records
- `dependent_tier`: contains metadata associated with an utterance 
- `transcript`: refers to one or more utterances
- `participant`: a person, usually corresponding to a labeled tier (MOT, CHI, etc.) 
- `corpus`: a collection of transcripts, generally corresponding to a specific research project
- `collection`: a collection of corpora, generally corresponding to a specific language

### Token
`id`: unique identifier  
`gloss`: natural language transcription  
`replacement`: replacement annotation  
`stem`: morphological form from CHILDES  
`part_of_speech`: part of speech  
`relation`: dependency information, from GRA or XGRA tier  
`speaker_id`: numeric identifier corresponding to participant.id  
`utterance_id`: integer index of utterance within transcript  
`token_order`: integer index of token within utterance  
`corpus_id`: numeric identifier corresponding to corpus.id  
`transcript_id`: numeric identifier correponding to transcript.id  
`speaker_age`: child age in days  
`speaker_code`: code on the CHILDES tier, e.g. MOT, FAT, INV, or CHI  
`speaker_name`: natural language designation for speaker  
`speaker_role`: speaker role as identified by the metadata  

### Utterance
### Dependent_tier
### Transcript
### Participant
### Corpus
### Collection


# Example Queries

get all tokens spoken by children between ages 400 and 600 days

`select t.gloss, t.speaker_age, p.name, p.corpus_id, p.code
from token t inner join participant p on t.speaker_id = p.id
where t.speaker_age between 400 and 600 and p.code = 'CHI'`


get all children under the age of 600 days and the number of times they said “eat” 

`select t.speaker_name, count(t.gloss), t.corpus_id
from token t inner join participant p on t.speaker_id = p.id
where t.stem like 'eat%'
and t.speaker_age < 600
and t.speaker_role = 'Target_Child'
group by t.speaker_id`


get all utterances longer than 20 words for a particular child

`select u.speaker_name, u.gloss, u.length, u.transcript_id
from utterance u 
where u.length > 20
and u.corpus_id = 23
and u.speaker_name = 'Alex'`


get all tokens from children with min_age < 2 years
`select *
from token t inner join participant p on t.speaker_id = p.id
where (p.role = 'Target_Child' or p.code = 'CHI')
and p.min_age < 730`

get all utterances from mothers and their children (with age of child for each utterance)

`select u.id as utterance_id, u.speaker_id, u.speaker_code, u.speaker_role, u.speaker_name, u.length, tr.target_child_id, tr.target_child_age from utterance u inner join transcript tr on u.transcript_id = tr.id
where u.speaker_role in (‘Target_Child’, ‘Mother’)`

