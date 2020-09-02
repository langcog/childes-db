#!/bin/bash
version=2020.1
childes_dir="/shared_hd1/childes-xml"
childes_url="https://childes.talkbank.org/data-xml/"
phonbank_dir="/shared_hd1/phonbank-xml"
phonbank_url="https://phonbank.talkbank.org/data-xml/"
python download_corpora.py --versions_root=$childes_dir --version=$version --base_url=$childes_url --name CHILDES
python download_corpora.py --versions_root=$phonbank_dir --version=$version --base_url=$phonbank_url --name Phonbank
