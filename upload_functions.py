# from werkzeug.utils import secure_filename
# from flask import url_for
import logging
import boto3
from botocore.exceptions import ClientError

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# UPLOAD_FOLDER = '/path/to/the/uploads'


# Checks that file has allowed extension
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def upload_file_obj(file_obj, bucket, object_name):
    """Upload a file to an S3 bucket

    :param file_name: File to upload
    :param bucket: Bucket to upload to
    :param object_name: S3 object name. If not specified then file_name is used
    :return: True if file was uploaded, else False
    """

    # If S3 object_name was not specified, use file_name
    # TODO: Name objects using some logic: listing_id+photos_1, etc.

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_fileobj(file_obj, bucket, object_name)
    except ClientError as e:
        logging.error(e)
        return False
    return True


def create_presigned_url(bucket_name, object_name, expiration=None):
    """Generate a presigned URL to share an S3 object

    :param bucket_name: string
    :param object_name: string
    :param expiration: Time in seconds for the presigned URL to remain valid
    :return: Presigned URL as string. If error, returns None.
    """

    # Generate a presigned URL for the S3 object
    s3_client = boto3.client('s3')
    try:
        response = s3_client.generate_presigned_url(
            'get_object',
            Params={
                    'Bucket': bucket_name,
                    'Key': object_name
                    },
            ExpiresIn=expiration
            )
    except ClientError as e:
        logging.error(e)
        return None

    # The response contains the presigned URL
    return response
