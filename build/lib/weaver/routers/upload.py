from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from moviepy.editor import VideoFileClip
from pydantic import BaseModel, validator
import re
import numpy as np
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

class UserName(BaseModel):
    username: str

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

router = APIRouter()
instruction = "Represent the cybersecurity content:"

@router.post("/upload/")
async def upload(file: UploadFile = File(...), file_type: FileType = Form(...), username: str = Form(...)):
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
    create_table_if_not_exists(username)

    if file_type == FileType.audio:
        result = await process_audio(username, file, file_type)
        return result
    elif file_type == FileType.video:
        result = await process_video(username, file, file_type)
        return result
    elif file_type == FileType.image:
        result = await process_image(username, file, file_type)
        return result
    elif file_type == FileType.text:
        result = await process_text(username, file, file_type)
        return result

    return {"success": "File processed successfully"}

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

def process_file(username, file_obj, file_key, file_type):
    """
    Process a given file by tokenizing the content and dividing it into chunks for further processing.

    Parameters:
        file_obj (dict): The file object containing the content to be processed.
        file_key (str): The key associated with the file.

    Returns:
        tuple: A tuple containing two lists - the local corpus and the local corpus embeddings.

    Note:
        - This function tokenizes the content, splits it into chunks, and processes each chunk.
        - It also handles UnicodeDecodeErrors and prints error messages for corrupted files.
    """
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
    header = {"file_key": file_key, "doc_id": doc_id, "file_type": file_type}
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
            insert_into_db(username, file_key, header, chunk_embedding, chunk_text)
        except Exception as e:
            logger.error(f"File corrupted: {file_key} Error: {e}")

    return local_corpus, local_corpus_embeddings

def create_table_if_not_exists(username):
    """
    Create a table in the database if it does not exist.

    Parameters:
        username (str): The username to be used as the table name. Must be alphanumeric.

    Returns:
        None

    Raises:
        HTTPException: If the username is not alphanumeric.

    Note:
        - This function checks whether a table with the given username already exists and creates it if not.
        - It prints messages to standard output for diagnostic purposes.
    """
    conn = get_connection()
    cursor = conn.cursor()
    table_name = username.replace('@', '__').replace('.', '_')

    # Check if the table already exists
    cursor.execute(f"SELECT to_regclass('{table_name}');")
    if cursor.fetchone()[0]:
        logger.warning(f"Table '{username}' already exists.")
        release_connection(conn)
        return

    create_table_query = f"""
        CREATE TABLE {table_name} (
            filename VARCHAR NOT NULL,
            metadata JSON,
            embeddings VECTOR(768),
            embeddings_text VARCHAR 
        );
    """

    try:
        cursor.execute(create_table_query)
        logger.info(f"Table '{table_name}' created successfully.")
    except Exception as e:
        logger.info(f"An error occurred while creating the '{table_name}' table: {e}")

    conn.commit()
    release_connection(conn)

def insert_into_db(username, filename, metadata, embeddings, embeddings_text):
    """
    Insert a record into the specified user's table.

    Parameters:
        username (str): The name of the table to insert the record into. Must be alphanumeric.
        filename (str): The name of the file associated with the record.
        metadata (dict): The metadata associated with the record.
        embeddings (list): The embeddings associated with the record.
        embeddings_text (str): The embeddings text associated with the record.

    Returns:
        None

    Raises:
        HTTPException: If the username is not alphanumeric.

    Note:
        - Prints messages to standard output for diagnostic purposes.
    """
    table_name = username.replace('@', '__').replace('.', '_')

    # Convert the embeddings to a numpy array
    embeddings_array = np.array(embeddings)

    # If the array is 2-D with a single row, flatten it to 1-D
    if embeddings_array.ndim == 2 and embeddings_array.shape[0] == 1:
        embeddings_array = embeddings_array.flatten()

    # Convert the numpy array to a Python list
    embeddings_list = embeddings_array.tolist()
    insert_query = f"""
        INSERT INTO {table_name} (filename, metadata, embeddings, embeddings_text)
        VALUES (%s, %s, %s, %s);
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(insert_query, (filename, json.dumps(metadata), embeddings_list, embeddings_text))
        logger.info(f"Record inserted successfully into '{table_name}' table.")
    except Exception as e:
        logger.info(f"An error occurred while inserting the record into the '{table_name}' table: {e}")
        raise

    connection.commit()
    release_connection(connection)