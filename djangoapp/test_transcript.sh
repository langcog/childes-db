source ~/.profile
echo "Creating new database..."
cd static
cat new_corpus_db.sql | mysql -u root -p"$ROOT_PASS"
echo "Enforcing schema..."
cd ../
python3 manage.py migrate db
echo "Populating....."
python3 manage.py test_single_transcript --data_source CHILDES --selected_collection XLing --corpus_name MDT --xml_dir /shared_hd2/childes-db/2020.1/candidate/childes.talkbank.org/data-xml/XLing/MDT/turkish/ta --fileid 18b_ctmd.xml
#python3 manage.py populate_db --data_source PhonBank --collection_root /shared_hd2/childes-db-xml/2020.1/candidate/phonbank.talkbank.org/data-xml --collection Eng-NA
