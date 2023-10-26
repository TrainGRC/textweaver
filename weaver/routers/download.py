from abc import ABC, abstractmethod
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks, Depends, Header
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

# In your upload function:
@router.post("/download/{username}/{file_key}")
async def upload(username: str, token: str = Depends(get_token), claims: dict = Depends(get_auth)):
    return "Success!"

@router.get("/download/list/{username}")
async def list_files(username: str, token: str = Depends(get_token), claims: dict = Depends(get_auth)):
    return "Success!"