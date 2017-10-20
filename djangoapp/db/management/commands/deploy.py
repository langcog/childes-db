import os
import boto3
from subprocess import call
from django.conf import settings
from django.core.management import BaseCommand, call_command


class Command(BaseCommand):
    help = "Repopulates local db and deploys new version of childes-db using boto3"

    def handle(self, *args, **options):

        # Drop all tables locally
        call_command('drop_tables')

        # Create new tables
        call_command('migrate')

        # Run XML parser and populate local db
        call_command('populate_db')

        # Connect to S3
        s3 = boto3.resource('s3')
        bucket = s3.Bucket(settings.S3_BUCKET_NAME)

        # Get new version name
        sqldump_name = get_new_db_version(bucket)

        # Connect to EC2 and create new instance
        ec2 = boto3.resource('ec2')
        instance = ec2.create_instances(ImageId=settings.EC2_AMI_ID, InstanceType=settings.EC2_INSTANCE_TYPE,
                                         SecurityGroupIds=[settings.EC2_SECURITY_GROUP_ID],
                                         KeyName=settings.EC2_KEY_NAME, MinCount=1, MaxCount=1)[0]

        # Create sqldump of local childes-db and zip
        call(['mysqldump', '-u', settings.DB_USER, '-p', settings.DB_PASSWORD, settings.DB_NAME, '|', 'gzip', '>',
              sqldump_name])

        instance.wait_until_running()
        instance.load()

        # Variables for later use
        key_file_path = os.path.join(settings.AWS_FOLDER_PATH, settings.EC2_KEY_NAME) + '.pem'
        user_at_hostname = '{}@{}'.format(settings.EC2_INSTANCE_USERNAME, instance.public_dns_name)

        # Copy sqldump to new instance
        call(['scp', '-o', 'StrictHostKeyChecking=no', 'i', key_file_path, sqldump_name, user_at_hostname])

        # Start MySQLd on new instance
        call(['ssh', '-i', key_file_path, user_at_hostname, '"sudo service mysqld start"'])

        # Import sqldump to db on new instance
        call(['ssh', '-i', key_file_path, user_at_hostname,
              '"zcat {} | mysql -u{} {}'.format(sqldump_name, settings.CHILDES_DB_USER, settings.CHILDES_DB_NAME)])

        # Send versioned sqldump to S3
        bucket.upload_file(sqldump_name, sqldump_name, ExtraArgs={'ACL': 'public-read'})

        # TODO Reassign EIP

        # TODO Test new db and destroy old instance


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
