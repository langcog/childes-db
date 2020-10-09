source ~/.profile
echo "Creating new database..."
cd static
cat new_dev_db_test.sql | mysql -u root -p"$ROOT_PASS" childes_db_dev_test
echo "Enforcing schema..."
cd ../
python3 manage.py migrate db
echo "Populating....."
python3 -m pdb -c c manage.py populate_db --data_source CHILDES --collection_root /shared_hd2/childes-db-xml/2020.1/candidate/childes.talkbank.org/data-xml --collection Eng-NA
