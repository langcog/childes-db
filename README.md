# childes-db
The childes-db project aims to make CHILDES transcripts more accessible by reducing the amount of preprocessing (e.g., CLAN or specific preprocessing libraries) and by making the individual tokens, utterances, transcripts, and corpora available in a tidy, tabular format that is accessible across programming languages. We release new versions of this dataset periodically to facilitate reproducibility. We also provide an R package (childesr) and a Python package (childespy) which allow users to access this database without having to write complex SQL queries.

# Preparing a New Release

The following instructions should work to generate a new release of `childes-db` on an Ubuntu 16 - 20 machine

### Preliminaries
- Confirm that you have 60+ gb free (newly downloaded material will be around 15 GB and new database will be 40 GB)
- Clone this repo and `cd` into it
- Make a virtual environment in, source it, and install requirements
```
virtualenv -p python3 childes-db-py3
source childes-db-py3/bin/activate
pip install -r requirements.txt
```
- Choose a new version name

### Download Corpora

Download corpora from the CHIILDES and PhonBank sites, both XML and CHAT files with the following Python script:

`python3 download_corpora.py --versions_root /shared_hd2/childes-db --version <version name, e.g. 2020.2>`


### MySQL Preparations

The following are necessary only if installing MySQL new 

Edit the mysqld.cnf file to make MySQL accessible externally and so that it can handle large queries and long import times better
`sudo vim /etc/mysql/mysql.conf.d/mysqld.cnf`

- change bind address to 0.0.0.0 to allow access from outside the host
`bind-address = 0.0.0.0`

- Increase the max_allowed_packed size
`max_allowed_packet      = 256M`

- Increase the default timeout
`wait_timeout=6000`

- Restart MySQL for changes to take effect

`sudo service mysql restart`

- On a production machine, ensure that there is a read-only user with the standard childes-db credentials

```
mysql -u<mysql username> -p<mysql password>
# should start MySQL prompt
create user 'childesdb'@'%' IDENTIFIED BY '<childes db default password>'
\q
```

### Machine Preparations

- On the production machine, make sure port 3306 is reachable through the security group (EC2) or other firewall

### Prepare the Schema 

Update the `config.json` file to point to the name of the database you want to populate. This is necessary in addition to 

`python3 manage.py makemigrations db`


### Initialize Schema and Populate

`./new_2020.sh`

This makes  a new database, runs migrate to to initialize the schema, and runs the `populate_db` command. As of the 2020 release, this calls the `populate_db` command twice internally: once to add datasets from CHILDES, and once to add datasets from Phonbank

### Testing

To compute the correlation between the Transcript-Speaker counts as computed with childes-db vs. that computed with CLAN:

`python3 manage.py test_frequency`

If this number is less than .997, check why.

### Deployment to EC2

To copy from the staging server, e.g., Chompsky, to the production server, e.g., EC2, copy databases to the production server with the following command

`ssh -p <ssh port on Chompsky> <user>@<chompsky_host> 'mysqldump -u <chompsky_username> -p<chompsky password>  --databases <database version> | gzip -c' | gunzip -c | mysql -u <EC2 MySQL uersname> -p<EC2 MySQL password>`

### Give Read-Only User Read Permissions

```
mysql -u<mysql username> -p<mysql password>
# should start MySQL prompt
GRANT SELECT ON `2020.1`.* TO '<mysql read-only user>'@'%' IDENTIFIED BY '<mysql  password>'
GRANT SELECT ON `2019.1`.* TO '<mysql read-only user>'@'%' IDENTIFIED BY '<mysql  password>'
GRANT SELECT ON `2018.1`.* TO '<mysql read-only user>'@'%' IDENTIFIED BY '<mysql  password>'
```

### Make unversioned childesdb database refer to most recent release

```
mysql -u<mysql username> -p<mysql password>
# should start MySQL prompt
create view admin as select * from `2020.1`.`admin`;
create view collection as select * from `2020.1`.`collection`;
create view corpus as select * from childesdb.`corpus`;
create view django_content_type as select * from `2018.1`.`django_content_type`;
create view django_migrations as select * from `2018.1`.`django_migrations`;
create view participant as select * from `2020.1`.`participant`;
create view token as select * from `2020.1`.`token`;
create view `token_frequency` as select * from `2018.1`.`token_frequency`;
create view transcript as select * from `2020.1`.`transcript`;
create view transcript_by_speaker as select * from `2018.1`.`transcript_by_speaker`;
create view utterance as select * from `2020.1`.`utterance`
\q
```

Give permissions to the the reader to read from the alias
```
mysql -u<mysql username> -p<mysql password>
# should start MySQL prompt
GRANT SELECT ON `childesdb`.* TO '<mysql read-only user>'@'%' IDENTIFIED BY '<mysql  password>'
GRANT SHOW VIEW ON `childesdb`.* TO '<mysql user>'@'%' IDENTIFIED BY '<mysql  password>'
```
