from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from moviepy.editor import VideoFileClip
from ksuid import ksuid
import tempfile
import json
import os
from enum import Enum
from ..config import get_connection, release_connection, model, tokenizer, logger, whisper_model
from nltk.tokenize import sent_tokenize

class FileType(str, Enum):
    audio = "audio"
    video = "video"
    image = "image"
    text = "text"

router = APIRouter()
instruction = "Represent the cybersecurity content:"

@router.post("/upload/")
async def upload(file: UploadFile = File(...), file_type: FileType = Form(...)):
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
        - If an error occurs during text file processing (e.g., UnicodeDecodeError), an error message is logged.
        - If the file is corrupted or there's an error in database insertion (to be implemented), an error message is printed.
        
    Note:
        - The functions for processing audio, video, and image files are placeholders and need further implementation.
        - The insert_into_db function (for inserting chunks into the database) needs to be implemented.
        - Specific error responses should be handled based on the requirements of the application.
    """
    if file_type == FileType.audio:
        result = await process_audio(file)
        return result
    elif file_type == FileType.video:
        result = await process_video(file)
        return result
    elif file_type == FileType.image:
        result = await process_image(file)
        return result
    elif file_type == FileType.text:
        result = await process_text(file)
        return result

    return {"success": "File processed successfully"}

async def process_audio(file: UploadFile):
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
        logger.info(f"Transcription result: {transcription_text}")
        # Process the transcription result using the process_file function
        process_file({'Body': transcription_text}, file.filename)
        return {"success": "Text processed successfully"}

    except Exception as e:
        logger.error(f"Error processing audio file: {file.filename} Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing audio file")

    finally:
        # Remove the temporary file
        os.unlink(temp_file.name)

async def process_video(file: UploadFile):
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
        result = await process_audio(temp_audio_upload_file)
        return {"success": "Text processed successfully"}

    except Exception as e:
        logger.error(f"Error processing video file: {file.filename} Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing video file")

    finally:
        # Remove the temporary files
        os.unlink(temp_video_file.name)
        os.unlink(temp_audio_file.name)

async def process_image(file: UploadFile):
    pass

async def process_text(file: UploadFile):
    # Read the file content
    text_content = (await file.read()).decode()
    file_key = file.filename

    process_file({'Body': text_content}, file_key)
    return {"success": "Text processed successfully"}

def process_file(file_obj, file_key):
    logger.info(f"Started Processing: {file_key}")
    doc_id = str(ksuid())
    local_corpus = []
    local_corpus_embeddings = []

    # Decode the content and handle any UnicodeDecodeError
    try:
        body_content = file_obj['Body']
    except UnicodeDecodeError:
        logger.error(f"UnicodeDecodeError: {file_key}")
        return local_corpus, local_corpus_embeddings
    max_chunk_size = 256  # Adjust as needed
    sentences = sent_tokenize(body_content)

    chunks = []
    chunk = []
    num_tokens = 0

    # Tokenize the sentences and split them into chunks
    for sentence in sentences:
        sentence_tokens = tokenizer.tokenize(sentence)
        if num_tokens + len(sentence_tokens) > max_chunk_size:
            chunks.append(chunk)
            chunk = [sentence]
            num_tokens = len(sentence_tokens)
        else:
            chunk.append(sentence)
            num_tokens += len(sentence_tokens)

    if chunk:
        chunks.append(chunk)

    # Process the chunks and insert them into the database
    for chunk in chunks:
        chunk_text = ' '.join(chunk)
        chunk_embedding = model.encode([[instruction, chunk_text]])  # Adjust 'instruction' as needed
        try:
            logger.info(f"Inserting into DB: {file_key}")
            #TODO: implement - insert_into_db(file_key, header, chunk_embedding, chunk_text)
        except Exception as e:
            print(f"File corrupted: {file_key} Error: {e}")

    return local_corpus, local_corpus_embeddings