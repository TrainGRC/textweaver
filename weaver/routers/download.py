from abc import ABC, abstractmethod
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks, Depends, Header
from starlette.responses import FileResponse, StreamingResponse
from moviepy.editor import VideoFileClip
import tempfile
import os
import io
import boto3
import botocore
import magic
from enum import Enum
from pdf2image import convert_from_path
from ..config import logger, whisper_model, textract_client, aws_session
from ..utils.embeddings import process_file
from ..utils.auth import get_auth

router = APIRouter()
s3_client = aws_session.client('s3')
        
async def get_token(authorization: str = Header(None)):
    if authorization:
        scheme, _, token = authorization.partition(' ')
        if scheme.lower() == 'bearer':
            return token
    raise HTTPException(status_code=401, detail='Unauthorized')

@router.get("/downloads/{username}/list")
async def list_files(username: str, token: str = Depends(get_token), claims: dict = Depends(get_auth)):
    username = claims.get('cognito:username')
    subscription_level = claims.get('custom:subscription')
    if subscription_level != 'ProMonthly' and subscription_level != 'ProYearly':
        raise HTTPException(status_code=403, detail="You must have a Pro subscription to list files.")
    try:
        user_pool_id = os.getenv('AWS_USER_POOL_ID')
        identity_pool_id = os.getenv('AWS_IDENTITY_POOL_ID')
        login_provider = os.getenv('AWS_USER_POOL_CLIENT_ID')
        region = os.getenv('AWS_COGNITO_REGION')
        id_token = token
        client = boto3.client('cognito-identity', region_name=region)
        
        # Get identity id for user
        response = client.get_id(
            IdentityPoolId=identity_pool_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
            }
        )
        identity_id = response['IdentityId']
        logger.info(f"Cognito Identity ID: {identity_id}")
        # Get credentials for identity id
        credentials_response = client.get_credentials_for_identity(
            IdentityId=identity_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
            }
        )            
        credentials = credentials_response['Credentials']
        access_key = credentials['AccessKeyId']
        secret_key = credentials['SecretKey']
        session_token = credentials['SessionToken']
        
    except Exception as e:
        logger.error(f"Unable to exchange token for temporary access key credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to exchange token for temporary access key credentials")

    # Create a boto3 session with the temporary access key credentials
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token
    )
    logger.info(f"Temporary access key credentials created for {username}")
    s3 = session.client('s3')
    s3_bucket = os.getenv('AWS_USER_FILES_BUCKET')
    s3_prefix = f'private/{identity_id}/files/'

    # List objects in the bucket with the prefix
    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=s3_bucket, Prefix=s3_prefix)

    # Collect all file keys and sort them in order of most recent
    file_keys = []
    for page in pages:
        for obj in page['Contents']:
            file_keys.append(obj['Key'])
    file_keys.sort(key=lambda x: x.split('/')[-1], reverse=True)

    return file_keys


# In your download function:
@router.post("/downloads/{username}/{file_key}")
async def upload(username: str, file_key: str, token: str = Depends(get_token), claims: dict = Depends(get_auth)):
    username = claims.get('cognito:username')
    subscription_level = claims.get('custom:subscription')
    if subscription_level != 'ProMonthly' and subscription_level != 'ProYearly':
        raise HTTPException(status_code=403, detail="You must have a Pro subscription to upload files.")
    try:
        user_pool_id = os.getenv('AWS_USER_POOL_ID')
        identity_pool_id = os.getenv('AWS_IDENTITY_POOL_ID')
        login_provider = os.getenv('AWS_USER_POOL_CLIENT_ID')
        region = os.getenv('AWS_COGNITO_REGION')
        id_token = token
        client = boto3.client('cognito-identity', region_name=region)
        
        # Get identity id for user
        response = client.get_id(
            IdentityPoolId=identity_pool_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
            }
        )
        identity_id = response['IdentityId']
        logger.info(f"Cognito Identity ID: {identity_id}")
        # Get credentials for identity id
        credentials_response = client.get_credentials_for_identity(
            IdentityId=identity_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
            }
        )            
        credentials = credentials_response['Credentials']
        access_key = credentials['AccessKeyId']
        secret_key = credentials['SecretKey']
        session_token = credentials['SessionToken']
        
    except Exception as e:
        logger.error(f"Unable to exchange token for temporary access key credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to exchange token for temporary access key credentials")

    # Create a boto3 session with the temporary access key credentials
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token
    )
    logger.info(f"Temporary access key credentials created for {username}")
    s3 = session.client('s3')
    s3_bucket = os.getenv('AWS_USER_FILES_BUCKET')
    s3_key = f'private/{identity_id}/files/{file_key}'

    # Download the file to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        s3.download_fileobj(s3_bucket, s3_key, tmp)
        tmp_path = tmp.name

    # Return the file as a StreamingResponse
    return FileResponse(tmp_path, media_type='application/octet-stream', filename=file_key)

@router.delete("/downloads/{username}/{file_key}")
async def delete_file(username: str, file_key: str, token: str = Depends(get_token), claims: dict = Depends(get_auth)):
    username = claims.get('cognito:username')
    subscription_level = claims.get('custom:subscription')
    if subscription_level != 'ProMonthly' and subscription_level != 'ProYearly':
        raise HTTPException(status_code=403, detail="You must have a Pro subscription to delete files.")
    try:
        user_pool_id = os.getenv('AWS_USER_POOL_ID')
        identity_pool_id = os.getenv('AWS_IDENTITY_POOL_ID')
        login_provider = os.getenv('AWS_USER_POOL_CLIENT_ID')
        region = os.getenv('AWS_COGNITO_REGION')
        id_token = token
        client = boto3.client('cognito-identity', region_name=region)
        
        # Get identity id for user
        response = client.get_id(
            IdentityPoolId=identity_pool_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
            }
        )
        identity_id = response['IdentityId']
        logger.info(f"Cognito Identity ID: {identity_id}")
        # Get credentials for identity id
        credentials_response = client.get_credentials_for_identity(
            IdentityId=identity_id,
            Logins={
                f'cognito-idp.{region}.amazonaws.com/{user_pool_id}': id_token
            }
        )            
        credentials = credentials_response['Credentials']
        access_key = credentials['AccessKeyId']
        secret_key = credentials['SecretKey']
        session_token = credentials['SessionToken']
        
    except Exception as e:
        logger.error(f"Unable to exchange token for temporary access key credentials: {str(e)}")
        raise HTTPException(status_code=500, detail="Unable to exchange token for temporary access key credentials")

    # Create a boto3 session with the temporary access key credentials
    session = boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token
    )
    logger.info(f"Temporary access key credentials created for {username}")
    s3 = session.client('s3')
    s3_bucket = os.getenv('AWS_USER_FILES_BUCKET')
    s3_key = f'private/{identity_id}/files/{file_key}'

    # Delete the specified file
    s3.delete_object(Bucket=s3_bucket, Key=s3_key)

    return {"detail": "File successfully deleted"}