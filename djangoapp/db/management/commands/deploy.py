import os
import boto3
from django.conf import settings
from django.core.management import BaseCommand, call_command
from db.models import Admin


class Command(BaseCommand):
    help = "On admin server: drops tables, rebuilds db from xml, create new instance, send sqldump and populate"

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

        # TODO use version from database
        # Get new version name
        sqldump_version = get_new_db_version(bucket)
        sqldump_name = 'childes-db-version-' + sqldump_version + '.sql.gz'

        # Add version to db
        #TODO duplicate?
        Admin.objects.create(
            version=sqldump_version
        )

        # Connect to EC2 and create new instance
        ec2 = boto3.resource('ec2')
        instance = ec2.create_instances(ImageId=settings.EC2_AMI_ID, InstanceType=settings.EC2_INSTANCE_TYPE,
                                         SecurityGroupIds=[settings.EC2_SECURITY_GROUP_ID],
                                         KeyName=settings.EC2_KEY_NAME, MinCount=1, MaxCount=1)[0]

        # Create sqldump of local childes-db and zip
        os.system("mysqldump -u{} -p{} {} | gzip > {}".format(
            settings.DB_USER, settings.DB_PASSWORD, settings.DB_NAME, sqldump_name
        ))

        instance.wait_until_running()
        instance.load()

        # Variables for later use
        key_file_path = os.path.join(settings.AWS_FOLDER_PATH, settings.EC2_KEY_NAME) + '.pem'
        user_at_hostname = '{}@{}'.format(settings.EC2_INSTANCE_USERNAME, instance.public_dns_name)

        # Copy sqldump to new instance
        os.system("scp -o StrictHostKeyChecking=no -i {} {} {}:".format(
            key_file_path, sqldump_name, user_at_hostname
        ))

        # Start MySQLd on new instance
        os.system('ssh -i {} -o StrictHostKeyChecking=no {} "sudo service mysqld start"'.format(key_file_path, user_at_hostname))

        # Import sqldump to db on new instance
        os.system('ssh -i {} -o StrictHostKeyChecking=no {} "zcat {} | sed \'s/datetime(6)/datetime/g\' | mysql -u{} -p{} {}"'.format(
            key_file_path, user_at_hostname, sqldump_name, settings.CHILDES_DB_USER, settings.CHILDES_DB_PASSWORD,
            settings.CHILDES_DB_NAME
        ))

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
    return '.'.join(numbers)
