import os
from ksuid import ksuid
from datetime import datetime
import numpy as np
from nltk.tokenize import sent_tokenize
from ..config import logger, model, tokenizer
from ..utils.db import batch_insert_into_pinecone

def validate_date(date_str: str, format: str = "%Y-%m-%d") -> str:
    try:
        datetime.strptime(date_str, format)
        return date_str
    except ValueError:
        return ""

def prepare_record_for_upsert(file_key, header, chunk_no, embeddings, embeddings_text):
    try:
        # Convert the embeddings to a numpy array
        embeddings_array = np.array(embeddings)
        # If the array is 2-D with a single row, flatten it to 1-D
        if embeddings_array.ndim == 2 and embeddings_array.shape[0] == 1:
            embeddings_array = embeddings_array.flatten()
        # Extract and validate metadata
        base_title = os.path.splitext(file_key)[0]
        title = f"{base_title} Part {chunk_no}"
        base_doc_id = header.get('doc_id', None)
        doc_id = f"{base_doc_id}-{chunk_no}" if base_doc_id else ksuid()
        publication_date_raw = header.get('PublicationDate', None)
        if isinstance(publication_date_raw, list):
            publication_date_raw = publication_date_raw[0]
        publication_date = validate_date(str(publication_date_raw))

        # Validate types
        if doc_id is None or not isinstance(embeddings_array.tolist(), list) or not isinstance(title, str):
            raise ValueError("Invalid data type")

        # Convert the numpy array to a Python list
        embeddings_list = embeddings_array.tolist()

        # Prepare metadata
        metadata = {
            "Title": title if title else "unknown",
            "Filename": file_key if file_key else "unknown",
            "PublicationDate": publication_date if publication_date else datetime.now().strftime("%Y-%m-%d"),
            "text": embeddings_text if embeddings_text else "unknown",
            "doc_id": base_doc_id if base_doc_id else "unknown"
        }

        return (doc_id, embeddings_list, metadata)
    except Exception as e:
        logger.error(f"An error occurred while preparing data for {file_key}: {e}")
        return None
    
def process_file(username, file_obj, file_key, file_type):
    """
    Process a given file by tokenizing the content and dividing it into chunks, then generating a batch of records for upsert.

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
    instruction = "passage:"
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
    header = {"doc_id": doc_id, "file_key": file_key, "file_type": file_type}
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

    records_to_upsert = []
    chunk_no = 0
    # Process the chunks and insert them into the database
    for chunk in chunks:
        chunk_no += 1
        chunk_text = ' '.join(chunk)
        chunk_embedding = model.encode([f"{instruction} {chunk_text}"])
        # Prepare each record for upsert but do not upsert it yet
        record = prepare_record_for_upsert(file_key, header, chunk_no, chunk_embedding, chunk_text)
        if record is not None:
            records_to_upsert.append(record)
    # Check if records_to_upsert is empty or None
    if not records_to_upsert:
        logger.error(f"An error occurred while processing the file {file_key}: No records to upsert")
        raise ValueError(f"An error occurred while processing the file {file_key}: No records to upsert")
    # Batch upsert records
    try:
        batch_insert_into_pinecone(file_key, username, records_to_upsert)
    except Exception as e:
        logger.error(f"An error occurred while inserting into Pinecone for {file_key}: {e}")
        return str(e), None
    return doc_id, file_key