from abc import ABC, abstractmethod
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks, Depends
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

class FileType(Enum):
    audio = "audio"
    video = "video"
    image = "image"
    pdf = "pdf"
    text = "text"

class FileProcessor(ABC):
    @abstractmethod
    async def process(self, username, file: UploadFile, file_type: FileType):
        pass

class AudioProcessor(FileProcessor):
    async def process(self, background_tasks: BackgroundTasks, username, file: UploadFile, file_type: FileType):
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        content = file.file.read()
        temp_file.write(content)
        temp_file.close()
        mime_type = magic.from_file(temp_file.name, mime=True)
        if mime_type != 'audio/mpeg':
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload a valid audio file.")
        result = whisper_model.transcribe(temp_file.name)
        transcription_text = result['text']
        try:
            doc_id, original_filename = process_file(username, {'Body': transcription_text}, file.filename, file_type)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"success": "Audio processing started", "doc_id": doc_id, "original_filename": original_filename}


class VideoProcessor(FileProcessor):
    async def process(self, background_tasks: BackgroundTasks, username, file: UploadFile, file_type: FileType):
        temp_video_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        content = file.file.read()
        temp_video_file.write(content)
        temp_video_file.close()
        mime_type = magic.from_file(temp_video_file.name, mime=True)
        if mime_type != 'video/mp4':
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload a valid video file.")
        video_clip = VideoFileClip(temp_video_file.name)
        audio_clip = video_clip.audio
        temp_audio_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        audio_clip.write_audiofile(temp_audio_file.name)
        temp_audio_file.close()
        temp_audio_upload_file = UploadFile(filename=file.filename, file=open(temp_audio_file.name, 'rb'))
        audio_processor = AudioProcessor()
        await audio_processor.process(background_tasks, username, temp_audio_upload_file, file_type)
        return {"success": "Video processing started"}

class ImageProcessor(FileProcessor):
    async def process(self, background_tasks: BackgroundTasks, username, file: UploadFile, file_type: FileType):
        # Validate file format
        assert file.filename.endswith(('.jpg', '.png', '.tiff')), "Invalid file format. Please upload a JPG, PNG, or TIFF file."
        
        # Read file content
        content = await file.read()
        
        # Use python-magic to check mime type
        mime_type = magic.from_buffer(content, mime=True)
        if mime_type not in ['image/jpeg', 'image/png', 'image/tiff']:
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload a valid image file.")
        
        # Use Textract client to detect text in the image
        response = textract_client.detect_document_text(Document={'Bytes': content})
        
        # Extract text from the response
        text_content = ""
        for item in response["Blocks"]:
            if item["BlockType"] == "LINE":
                text_content += item["Text"] + "\n"
        
        # Process the extracted text
        try:
            doc_id, original_filename = process_file(username, {'Body': text_content}, file.filename, file_type)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"success": "Image processing complete", "doc_id": doc_id, "original_filename": original_filename}

class PDFProcessor(FileProcessor):
    async def process(self, background_tasks: BackgroundTasks, username, file: UploadFile, file_type: FileType):
        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        content = await file.read()
        temp_file.write(content)
        temp_file.close()
        mime_type = magic.from_file(temp_file.name, mime=True)
        if mime_type != 'application/pdf':
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload a valid PDF file.")
        text_content = ""
        try:
            with open(temp_file.name, 'rb') as pdf_file:
                response = textract_client.detect_document_text(Document={'Bytes': pdf_file.read()})
            for item in response["Blocks"]:
                if item["BlockType"] == "LINE":
                    text_content += item["Text"] + "\n"
        except textract_client.exceptions.UnsupportedDocumentException as error:
            # If the PDF is not valid, convert the pages into images and process them as images
            images = convert_from_path(temp_file.name)
            image_files = []  # List to keep track of image files
            for i, image in enumerate(images):
                image_filename = f'{file.filename}_{i}.jpg'
                image.save(image_filename, 'JPEG')
                image_files.append(image_filename)  # Add the image file to the list
                try:
                    with open(image_filename, 'rb') as image_file:
                        response = textract_client.detect_document_text(Document={'Bytes': image_file.read()})
                        for item in response["Blocks"]:
                            if item["BlockType"] == "LINE":
                                text_content += item["Text"] + "\n\n"
                except Exception as error:
                    logger.error(f"Error processing image file: {error}")
                    raise HTTPException(status_code=500, detail="Error processing image file")
                finally:
                    # Delete the image file
                    os.remove(image_filename)
            # Delete the temporary PDF file
            os.remove(temp_file.name)
        except Exception as error:
            logger.error(f"Unexpected error: {error}")
            raise HTTPException(status_code=500, detail="Unexpected error processing PDF file")
        try:
            doc_id, original_filename = process_file(username, {'Body': text_content}, file.filename, file_type)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"success": "PDF processing complete", "doc_id": doc_id, "original_filename": original_filename}

class TextProcessor(FileProcessor):
    async def process(self, background_tasks: BackgroundTasks, username, file: UploadFile, file_type: FileType):
        text_content = (await file.read()).decode()
        mime_type = magic.from_buffer(text_content, mime=True)
        if mime_type != 'text/plain':
            raise HTTPException(status_code=400, detail="Invalid file type. Please upload a valid text file.")
        file_key = file.filename
        try:
            doc_id, original_filename = process_file(username, {'Body': text_content}, file.filename, file_type)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=str(e))
        return {"success": "Text processing complete", "doc_id": doc_id, "original_filename": original_filename}

class FileProcessorFactory:
    def get_processor(self, file_type: FileType) -> FileProcessor:
        if file_type == FileType.audio:
            return AudioProcessor()
        elif file_type == FileType.video:
            return VideoProcessor()
        elif file_type == FileType.image:
            return ImageProcessor()
        elif file_type == FileType.pdf:
            return PDFProcessor()
        elif file_type == FileType.text:
            return TextProcessor()
        else:
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")
        
# In your upload function:
@router.post("/upload")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...), file_type: str = Form(...), claims: dict = Depends(get_auth)):
    username = claims.get('cognito:username')
    subscription_level = claims.get('custom:subscription')
    if subscription_level != 'ProMonthly' and subscription_level != 'ProYearly':
        raise HTTPException(status_code=403, detail="You must have a Pro subscription to upload files.")
    try:
        file_type_enum = FileType(file_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid file type: {file_type}")
    s3_bucket = os.getenv('AWS_USER_FILES_BUCKET')
    s3_key = f'{username}/files/{file.filename}'
    file_content = await file.read()  # Read the file content into a variable
    s3_client.upload_fileobj(io.BytesIO(file_content), s3_bucket, s3_key)  # Upload the file content to S3
    file.file = io.BytesIO(file_content)  # Replace the file's file object with a new file object created from the file content
    processor = FileProcessorFactory().get_processor(file_type_enum)
    result = await processor.process(background_tasks, username, file, file_type_enum)
    return result