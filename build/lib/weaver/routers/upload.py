from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks
from moviepy.editor import VideoFileClip
from pydantic import BaseModel, validator, Field
import PyPDF2
import mutagen
import re
import tempfile
import os
from enum import Enum
from ..config import model, tokenizer, logger, whisper_model
from ..utils.db import create_user_table
from ..utils.embeddings import process_file

router = APIRouter()

class FileType(str, Enum):
    audio = "audio"
    video = "video"
    image = "image"
    text = "text"

class UserName(BaseModel):
    username: str = Field(..., description="Username for the upload. Must be an alphanumeric value or a valid email address.")

    @validator("username", allow_reuse=True)
    def validate_user_table(cls, username):
        if username is not None:
            if not username.isalnum():
                # Check if it's a valid email pattern
                pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                if not re.match(pattern, username):
                    raise ValueError("username must be an alphanumeric value or a valid email address.")
            username = username.replace('@', '__').replace('.', '_')  # Replacing both @ and . with _
        return username

def validate_file_content(file_type: FileType, file: UploadFile) -> str:
    try:
        # Read the file content
        file_content = file.file.read()

        if file_type == FileType.audio:
            # Validate MP3 file using mutagen
            mutagen.File(file_content)
        elif file_type == FileType.video:
            # Validate MP4 file using moviepy
            VideoFileClip(file_content)
        elif file_type == FileType.text and file.filename.endswith('.pdf'):
            # Validate PDF file using PyPDF2
            PyPDF2.PdfFileReader(file_content)

        return ""
    except:
        return f"Invalid content for file type {file_type.value}"

def validate_file_type(file_type: FileType, file_extension: str) -> str:
    if file_type == FileType.audio and file_extension != '.mp3':
        return "Invalid file type for audio"
    elif file_type == FileType.video and file_extension != '.mp4':
        return "Invalid file type for video"
    elif file_type == FileType.image and file_extension not in ['.jpg', '.png']:
        return "Invalid file type for image"
    elif file_type == FileType.text and file_extension not in ['.pdf', '.txt']:
        return "Invalid file type for text"
    return ""

ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.png', '.txt', '.mp3', '.mp4'}

@router.post("/upload/")
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...), file_type: FileType = Form(...), username: str = Form(...)):
    """
    Endpoint to upload and process different types of files: audio, video, image, and text.

    Takes an uploaded file and an optional file type parameter.

    Parameters:
        file (UploadFile): The file object uploaded by the user.
        file_type (FileType, optional): The type of the file being uploaded. Default to None.
                                        Accepted values: "audio", "video", "image", "text".
                                        Example usage with curl:
                                        curl -X 'POST' 'http://127.0.0.1:8000/upload' \
                                            -H 'Content-Type: multipart/form-data' \
                                            -F 'file=@path/to/yourfile.txt' \
                                            -F 'file_type=text'

    Returns:
        dict: A dictionary containing a success message if the file was processed successfully.
        Example:
        {
            "success": "File processed successfully"
        }

    Errors:
        - If the username is not alphanumeric or an e-mail address, an error message is returned.
        - If an error occurs during text file processing (e.g., UnicodeDecodeError), an error message is logged.
        - If the file is corrupted or there's an error in database insertion (to be implemented), an error message is logged.
        
    Note:
        - The functions for processing audio, video, and image files are placeholders and need further implementation.
        - The insert_into_db function (for inserting chunks into the database) needs to be implemented.
        - Specific error responses should be handled based on the requirements of the application.
    """

    # Validate Username is e-mail address or only alphanumeric
    username_model = UserName(username=username) # Trigger the validation

    # Check if the table exists, and create it if not
    create_user_table(username)

    # Check file extension
    file_extension = os.path.splitext(file.filename)[1]
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension")
    # validation_error_msg = validate_file_type(file_type, file_extension) or validate_file_content(file_type, file)
    # if validation_error_msg:
    #     raise HTTPException(status_code=400, detail=validation_error_msg)

    # Add the processing function as a background task
    if file_type == FileType.audio:
        background_tasks.add_task(process_audio, username, file, file_type)
    elif file_type == FileType.video:
        background_tasks.add_task(process_video, username, file, file_type)
    elif file_type == FileType.image:
        background_tasks.add_task(process_image, username, file, file_type)
    elif file_type == FileType.text:
        background_tasks.add_task(process_text, username, file, file_type)

    return {"success": "File processing has started"}

async def process_image(username, file: UploadFile, file_type: FileType):
    pass

async def process_audio(username, file: UploadFile, file_type: FileType):
    # Create a temporary file to store the uploaded audio
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        # Write the uploaded file to the temporary file
        content = file.file.read()
        temp_file.write(content)
        temp_file.close()

        # Transcribe the audio using the Whisper model
        result = whisper_model.transcribe(temp_file.name)
        transcription_text = result['text']
        # Process the transcription result using the process_file function
        process_file(username, {'Body': transcription_text}, file.filename, file_type)
        return {"success": "Text processed successfully"}

    except Exception as e:
        logger.error(f"Error processing audio file: {file.filename} Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing audio file")

    finally:
        # Remove the temporary file
        os.unlink(temp_file.name)

async def process_video(username, file: UploadFile, file_type: FileType):
    # Create a temporary file to store the uploaded video
    temp_video_file = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        # Write the uploaded file to the temporary video file
        content = file.file.read()
        temp_video_file.write(content)
        temp_video_file.close()

        # Load the video using moviepy and extract the audio
        video_clip = VideoFileClip(temp_video_file.name)
        audio_clip = video_clip.audio

        # Create a temporary file to store the extracted audio
        temp_audio_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        audio_clip.write_audiofile(temp_audio_file.name)
        temp_audio_file.close()

        # Create a temporary UploadFile object for the extracted audio
        temp_audio_upload_file = UploadFile(filename=file.filename, file=open(temp_audio_file.name, 'rb'))

        # Process the audio using the existing process_audio function
        result = await process_audio(username, temp_audio_upload_file, file_type)
        return {"success": "Text processed successfully"}

    except Exception as e:
        logger.error(f"Error processing video file: {file.filename} Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing video file")

    finally:
        # Remove the temporary files
        os.unlink(temp_video_file.name)
        os.unlink(temp_audio_file.name)

async def process_text(username, file: UploadFile, file_type: FileType):
    # Read the file content
    text_content = (await file.read()).decode()
    file_key = file.filename

    process_file(username, {'Body': text_content}, file_key, file_type)
    return {"success": "Text processed successfully"}