source ~/.profile
echo "Creating new database..."
cd static
cat cabnc_22.sql | mysql -u root -p"$ROOT_PASS"
echo "Enforcing schema..."
cd ../
python3 manage.py migrate db
echo "Populating....."
python3 manage.py populate_db --data_source CABNC --collection_root /shared_hd1/cabnc-xml/saulalbert-CABNC-0a28a11/data/cabnc_talkbank_xml

# python3 -m pdb -c c
