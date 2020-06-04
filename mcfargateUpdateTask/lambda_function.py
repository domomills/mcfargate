import json
import boto3
import botocore
from boto3.session import Session
from zipfile import ZipFile
import os

ecs = boto3.client('ecs')
code_pipeline = boto3.client('codepipeline')

def setup_s3_client(job_data):
    key_id = job_data['artifactCredentials']['accessKeyId']
    key_secret = job_data['artifactCredentials']['secretAccessKey']
    session_token = job_data['artifactCredentials']['sessionToken']

    session = Session(aws_access_key_id=key_id,
        aws_secret_access_key=key_secret,
        aws_session_token=session_token)
    return session.client('s3', config=botocore.client.Config(signature_version='s3v4'))

def get_task_def(s3Client, artifact, job_id):
    try:
        bucketName = artifact['location']['s3Location']['bucketName']
        objectKey = artifact['location']['s3Location']['objectKey']
        os.chdir('/tmp')
        s3Client.download_file(bucketName, objectKey, 'artifact.zip')
        print('Artifact zip file downloaded')
        with ZipFile('artifact.zip', 'r') as zipObj:
            zipObj.extractall()
        with open('task-definitions.json') as f:
            taskDef = json.load(f)
        print('task-definitions.json loaded')
        return taskDef
    except Exception as e:
        print('Retrieving task definition failed with exception.')
        print(e)
        put_job_failure(job_id)

def update_task_def(taskDef, job_id):
    try:
        ecs.register_task_definition(**taskDef)
        print('Task definition updated')
    except Exception as e:
        print('Updating task definition failed due to exception.')
        print(e)
        put_job_failure(job_id)


def put_job_success(job_id):
    print('Putting job success')
    code_pipeline.put_job_success_result(jobId=job_id)

def put_job_failure(job_id):
    print('Putting job failure')
    code_pipeline.put_job_failure_result(jobId=job_id, failureDetails={'message': 'Failed', 'type': 'JobFailed'})

def lambda_handler(event, context):
    try:
        job_id = event['CodePipeline.job']['id']
        job_data = event['CodePipeline.job']['data']
        artifact = job_data['inputArtifacts'][0]
        #setup the S3 client with credentials
        s3 = setup_s3_client(job_data)
        #get the task definition from S3
        taskDef = get_task_def(s3, artifact, job_id)
        #update task definition in ECS
        update_task_def(taskDef, job_id)
        #let CodePipeline know that the job was successful
        put_job_success(job_id)
    except Exception as e:
        print('Function failed due to exception')
        print(e)

    return 'Complete'
