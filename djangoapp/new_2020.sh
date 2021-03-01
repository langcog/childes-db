source ~/.profile
echo "Creating new database..."
cd static
cat new_2020.sql | mysql -u root -p"$ROOT_PASS"
echo "Enforcing schema..."
cd ../
python3 manage.py migrate db
echo "Populating....."
python3 manage.py populate_db --data_source CHILDES --collection_root /shared_hd2/childes-db/2020.1/candidate/childes.talkbank.org/data-xml > 2020_childes.log 
python3 manage.py populate_db --data_source PhonBank --collection_root /shared_hd2/childes-db/2020.1/candidate/phonbank.talkbank.org/data-xml > 2020_phonbank.log
