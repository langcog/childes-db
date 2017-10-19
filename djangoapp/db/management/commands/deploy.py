import os
import json
import boto3
from django.conf import settings
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Deploys new version of childes-db"

    def handle(self, *args, **options):

        collections = [
            'Eng-NA',
            'Eng-UK'
        ]

        # TODO specify path, collections(?) in config
        for collection in collections:
            call_command('populate_db', collection=collection,
                         path='/home/alsan/childes.talkbank.org/data-xml/{}'.format(collection))

        s3 = boto3.resource('s3')
        bucket = s3.Bucket('childes-db-archive')

        sqldump_name = get_new_db_version(bucket)

        # TODO do the dry run thing
        # TODO aws ids in config
        ec2 = boto3.resource('ec2')
        instance = ec2.create_instances(ImageId='ami-a88e4cd0',
                                        InstanceType='t2.medium',
                                        SecurityGroupIds=['sg-e77bba82'],
                                        KeyName='childes-db',
                                        MinCount=1,
                                        MaxCount=1)[0]

        db_user, db_password, db_name = get_mysql_credentials()

        # TODO os.system vs popen
        # TODO save them in common directory on chompsky, store path in config
        os.system('mysqldump -u {} -p{} {} | gzip > {}'.format(db_user, db_password, db_name, sqldump_name))

        instance.wait_until_running()
        instance.load()

        # Copy sqldump to new instance
        # TODO create childes-db user (not ec2-user) for these instances
        # TODO how to check if connection doesn't drop here
        # TODO check the host key warning
        os.system('scp -oStrictHostKeyChecking=no -i ~/.aws/childes-db.pem {} ec2-user@{}:'
                  .format(sqldump_name, instance.public_dns_name))

        # Start mysqld on new instance
        os.system('ssh -i ~/.aws/childes-db.pem ec2-user@{} "sudo service mysqld start"'.format(instance.public_dns_name))

        # Populate DB on new instance
        # TODO user / db name
        # TODO run in background?
        os.system('ssh -i ~/.aws/childes-db.pem ec2-user@{} "zcat {} | mysql -uroot childesdb"'
            .format(instance.public_dns_name, sqldump_name))

        # Send versioned sqldump to S3
        bucket.upload_file(sqldump_name, sqldump_name, ExtraArgs={'ACL': 'public-read'})

        # TODO Reassign EIP

        # TODO sanity check new db / destroy old db


def get_mysql_credentials():
    with open(os.path.join(settings.BASE_DIR, 'config.json')) as json_config_file:
        config = json.load(json_config_file)['mysql']
        return config['DB_USER'], config['DB_PASSWORD'], config['DB_NAME']


def get_new_db_version(bucket):
    files = list(bucket.objects.all())
    last_version = files[len(files) - 1].key
    numbers = last_version[19:24].split('.')
    numbers[2] = str(int(numbers[2]) + 1)
    if numbers[2] == '10':
        numbers[2] = '0'
        numbers[1] = str(int(numbers[1]) + 1)
    if numbers[1] == '10':
        numbers[1] = '0'
        numbers[0] = str(int(numbers[0]) + 1)
    return 'childes-db-version-' + '.'.join(numbers) + '.sql.gz'
