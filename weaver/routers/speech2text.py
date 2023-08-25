from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from ..config import model, tokenizer, logger, whisper_model
from ksuid import ksuid
from fastapi.responses import JSONResponse
from pydub.utils import mediainfo
import os
import tempfile
import asyncio


router = APIRouter()

async def background_process(file_name: str, ksuid_filename: str):
    logger.info(f"Processing audio file: {file_name}")
    try:
        os.makedirs('transcriptions', exist_ok=True)
        result = whisper_model.transcribe(file_name)
        transcription_text = result['text']
        with open(f"transcriptions/{ksuid_filename}.txt", "w") as file:
            file.write(transcription_text)
    except Exception as e:
        logger.error(f"Error processing audio file: {file_name} Error: {str(e)}")
    finally:
        os.unlink(file_name)

@router.post("/speech2text/")
async def speech2text(file: UploadFile = File(...), background_tasks: BackgroundTasks = None) -> JSONResponse:
    # Check file extension
    file_extension = os.path.splitext(file.filename)[1]
    if file_extension != '.mp3':
        raise HTTPException(status_code=400, detail="Unsupported file extension for audio")

    # Create a temporary file to store the uploaded audio
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    content = file.file.read()
    temp_file.write(content)
    temp_file.close()

    # Check audio length
    file_info = mediainfo(temp_file.name)
    duration = float(file_info["duration"])
    logger.info(f"Audio file duration: {duration}")
    if duration > 20:
        ksuid_filename = ksuid()
        background_tasks.add_task(background_process, temp_file.name, ksuid_filename)
        return JSONResponse(content={"status": "processing", "message": "File is being processed. Check back later.", "file_id": str(ksuid_filename)})
    else:
        try:
            result = whisper_model.transcribe(temp_file.name)
            transcription_text = result['text']
            return JSONResponse(content={"transcript": transcription_text})
        except Exception as e:
            logger.error(f"Error processing audio file: {file.filename} Error: {str(e)}")
            raise HTTPException(status_code=500, detail="Error processing audio file")
        finally:
            os.unlink(temp_file.name)

async def delete_file_with_delay(file_path: str, delay_seconds: int = 300):
    await asyncio.sleep(delay_seconds)  # Sleep for delay_seconds (e.g., 24 hours)
    try:
        os.unlink(file_path)
        logger.info(f"Deleted file: {file_path}")
    except Exception as e:
        logger.error(f"Error deleting file: {file_path}. Error: {str(e)}")

@router.get("/speech2text/{ksuid}")
async def get_transcription(ksuid: str, background_tasks: BackgroundTasks) -> JSONResponse:
    file_path = f"transcriptions/{ksuid}.txt"

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Transcription still processing or not found.")

    try:
        with open(file_path, "r") as file:
            transcription_text = file.read()

        # Schedule the file to be deleted after a delay
        background_tasks.add_task(delete_file_with_delay, file_path)

        return JSONResponse(content={"transcript": transcription_text})
    except Exception as e:
        logger.error(f"Error retrieving transcription file: {ksuid}. Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving transcription file. Please try again later.")