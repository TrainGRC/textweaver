from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks
from ..config import model, tokenizer, logger, whisper_model
from pydantic import BaseModel, validator, Field

router = APIRouter()
from fastapi.responses import JSONResponse

@router.post("/speech2text/")
async def speech2text(file: UploadFile = File(...)) -> JSONResponse:
    """
    Endpoint to upload an audio file and return the text transcript using Whisper AI.

    Parameters:
        file (UploadFile): The audio file object uploaded by the user in '.mp3' format.

    Returns:
        JSONResponse: A JSON response containing the transcript of the uploaded audio file.
    """
    # Check file extension
    file_extension = os.path.splitext(file.filename)[1]
    if file_extension != '.mp3':
        raise HTTPException(status_code=400, detail="Unsupported file extension for audio")

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
        return JSONResponse(content={"transcript": transcription_text})

    except Exception as e:
        logger.error(f"Error processing audio file: {file.filename} Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing audio file")

    finally:
        # Remove the temporary file
        os.unlink(temp_file.name)