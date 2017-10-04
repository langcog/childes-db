# childes-db

The CHILDES-db project aims to make [CHILDES](http://childes.talkbank.org/) transcripts more accessible by reducing the amount of preprocessing necessary (e.g., CLAN or specific preprocessing libraries) and by making the individual tokens and utterances available in a tabular format. In addition, we plan to release new dated versions periodically to facilitate replication (the public version of CHILDES currently does not have a versioning system); we are also working on an API (R and/or Pandas) to provide abstractions such that users do not need to write SQL to perform common tasks.

# Tables
Tables are split into primary tables, containing representations of the transcripts, and derived tables that contain cached values (for the `rchildes` API).  

### Primary Tables
- `token`: atomic construct, corresponding to a word. 
- `utterance`: refers to one or more token records. 
- `dependent_tier`: contains metadata associated with an utterance (to be implemented). 
- `transcript`: refers to one or more utterances. 
- `participant`: a person, usually corresponding to a labeled tier (MOT, CHI, etc.) 
- `corpus`: a collection of transcripts, generally corresponding to a specific research project. 
- `collection`: a collection of corpora, generally corresponding to a specific language

### Derived Tables
- `django_content_type`: used for Django configuration
- `django_migrations`: used for Django configuration
- `transcript_by_speaker`: type and token counts, MLU estimates for each participant in each transcript
- `token_frequency`: cached counts per type per child in transcript

### Token
`id`: unique identifier  
`gloss`: natural language transcription   
`replacement`: replacement annotation, if the gloss contains a nonstandard form  
`stem`: morphological form from CHILDES  
`part_of_speech`: part of speech  
`relation`: dependency information, from GRA or XGRA tier  
`speaker_id`: numeric identifier corresponding to participant.id  
`utterance_id`: numeric identifier correponding to utterance.id  
`token_order`: integer index of token within utterance  
`corpus_id`: numeric identifier corresponding to corpus.id  
`transcript_id`: numeric identifier correponding to transcript.id  
`speaker_age`: child age in days  
`speaker_code`: code on the CHILDES tier, e.g. MOT, FAT, INV, or CHI  
`speaker_name`: natural language designation for speaker  
`speaker_role`: speaker role as identified by the metadata  
`speaker_sex`: gender of participant  
`target_child_id`: numeric identifier corresponding to participant.id of target child  
`target_child_age`: age of the child at time of utterance  
`target_child_name`: name of the target child in the correpsonding transcript  
`target_child_sex`: gender of target child in the corresponding transcript  

### Utterance
`id`: unique identifier  
`speaker_id`: numeric identifier corresponding to participant.id  
`order`:  integer index of utterance within transcript  
`transcript_id`: numeric identifier correponding to transcript.id  
`corpus_id`: numeric identifier corresponding to corpus.id  
`gloss`: natural language transcription of the sentence  
`length`: number of word tokens in the utterance  
`relation`: dependency information for the utterance, from GRA or XGRA tier  
`stem`: concatenated stemmed representation (from the MOR tier) for the utterance  
`part_of_speech`: concatenated part of speech information for the utterance  
`speaker_code`: code on the CHILDES tier, e.g. MOT, FAT, INV, or CHI  
`speaker_name`: natural language designation for speaker  
`speaker_role`: speaker role as identified by the metadata  
`speaker_sex`: gender of participant  
`target_child_id`: numeric identifier corresponding to participant.id of target child  
`target_child_age`: age of the child at time of utterance   
`target_child_name`: name of the target child in the correpsonding transcript  
`target_child_sex`: gender of target child in the corresponding transcript  

### Dependent_tier
This table has not yet been implemented. `Dependent_tier` will contain an utterance-level annotation, e.g., a %PHO annotation with a specific `utterance_id`. 

### Transcript
`id`: unique identifier  
`languages`: included languages in the transcript  
`date`: Year, month and day of initial data collection  
`filename`: path in the corresponding CHILDES directory structure (paths like this may change with new releases)  
`corpus_id`: numeric identifier corresponding to corpus.id  
`target_child_id`: numeric identifier corresponding to participant.id of target child  
`target_child_age`: age of the child at time of utterance  
`target_child_name`: name of the target child in the correpsonding transcript  

### Participant
`id`: unique identifier  
`code`: code on the CHILDES tier, e.g. MOT, FAT, INV, or CHI  
`speaker_name`: natural language designation for speaker  
`speaker_role`: speaker role as identified by the metadata  
`language`: language associated with speaker  
`group`: group associated with speaker per transcript-level metadata  
`sex`: gender of a speaker per transcript-level metadata  
`education`: level of education of the speaker per transcript-level metadata  
`custom`: the custom field in  transcript-level metadata  
`corpus_id`: numeric identifier corresponding to corpus.id  
`max_age`: latest age in days for a transcript in the corpus; defined only for children   
`min_age`: earliest age in days for a transcript in the corpus; defined only for children  
`target_child_id`: participant.id of the target child, if unique across transcripts  

### Corpus
`id`: unique identifier  
`name`: corpus name  
`collection_id`: numeric identifier corresponding to collection.id  

### Collection
`id`: unique identifier  
`name`: collection name  

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

