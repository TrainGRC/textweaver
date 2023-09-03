from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks, Depends
from moviepy.editor import VideoFileClip
from pydantic import BaseModel, validator, Field
import botocore
import PyPDF2
import mutagen
import re
import tempfile
import os
from enum import Enum
from ..config import logger, whisper_model, textract_client
from ..utils.embeddings import process_file
from ..utils.auth import get_auth

router = APIRouter()

class FileType(str, Enum):
    audio = "audio"
    video = "video"
    image = "image"
    pdf = "pdf"
    text = "text"

def validate_file_content(file_type: FileType, file: UploadFile) -> str:
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = file.file.read()
            temp_file.write(content)
            temp_file.flush()

            if file_type == FileType.audio:
                mutagen.File(temp_file.name)  # Open audio file
            elif file_type == FileType.video:
                VideoFileClip(temp_file.name)  # Open video file
            elif file_type == FileType.text and file.filename.endswith('.pdf'):
                with open(temp_file.name, 'rb') as pdf_file:
                    PyPDF2.PdfFileReader(pdf_file)  # Open PDF file

        os.unlink(temp_file.name)  # Delete the temporary file
        return ""
    except:
        return f"File type validation failed for {file_type.value}."

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
async def upload(background_tasks: BackgroundTasks, file: UploadFile = File(...), file_type: FileType = Form(...), claims: dict = Depends(get_auth)):
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

    # Check file extension
    file_extension = os.path.splitext(file.filename)[1]
    if file_extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file extension")

    # Add the processing function as a background task
    username = claims.get('cognito:username')
    if file_type == FileType.audio:
        background_tasks.add_task(process_audio, username, file, file_type)
    elif file_type == FileType.video:
        background_tasks.add_task(process_video, username, file, file_type)
    elif file_type == FileType.image:
        background_tasks.add_task(process_image, username, file, file_type)
    elif file_type == FileType.pdf:
        await process_pdf(username, file, file_type)
    elif file_type == FileType.text:
        background_tasks.add_task(process_text, username, file, file_type)

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

async def process_pdf(username, file: UploadFile, file_type: FileType):
    """
    Process the uploaded PDF file using Amazon Textract.

    Parameters:
        username (str): The username associated with the upload.
        file (UploadFile): The uploaded PDF file object.
        file_type (FileType): The type of the file being uploaded (in this case, always FileType.text).

    Returns:
        dict: A dictionary containing a success message if the PDF was processed successfully.
    """
    # TODO: Add support for limiting pages of PDF to process
    # TODO: Add support for validating PDF prior to processing
    # Create a temporary file to store the uploaded PDF
    temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    try:
        # Write the uploaded file to the temporary file
        content = await file.read()
        temp_file.write(content)
        temp_file.close()

        # Open the PDF file and call Amazon Textract to process the PDF
        with open(temp_file.name, 'rb') as pdf_file:
            try:
                response = textract_client.detect_document_text(Document={'Bytes': pdf_file.read()})
            except textract_client.exceptions.UnsupportedDocumentException as error:
                logger.error(f"Unsupported document: {error}")
                raise HTTPException(status_code=400, detail="Unsupported document type. Please upload a valid PDF file.")
            except botocore.exceptions.ParamValidationError as error:
                logger.error(f"Parameter validation error: {error}")
                raise HTTPException(status_code=400, detail="Invalid parameters provided")
            except botocore.exceptions.ClientError as error:
                logger.error(f"Client error with Textract: {error}")
                raise HTTPException(status_code=500, detail="Error processing PDF file")
            except Exception as error:
                logger.error(f"Unexpected error: {error}")
                raise HTTPException(status_code=500, detail="Unexpected error processing PDF file")
            except Exception as error:
                logger.error(f"Unexpected error: {error}")
                raise HTTPException(status_code=500, detail="Unexpected error processing PDF file")

        # Extract the text from the Textract response
        text_content = ""
        for item in response["Blocks"]:
            if item["BlockType"] == "LINE":
                text_content += item["Text"] + "\n"
        logger.info(f"Extracted text from PDF file: {file.filename}")
        logger.info(f"Extracted text: {text_content}")
        # Process the extracted text using the process_file function
        process_file(username, {'Body': text_content}, file.filename, file_type)
        return {"success": "PDF processed successfully"}

    finally:
        # Remove the temporary file
        os.unlink(temp_file.name)

async def process_text(username, file: UploadFile, file_type: FileType):
    # Read the file content
    text_content = (await file.read()).decode()
    file_key = file.filename

    process_file(username, {'Body': text_content}, file_key, file_type)
    return {"success": "Text processed successfully"}