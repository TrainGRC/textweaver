import json
from ksuid import ksuid
from nltk.tokenize import sent_tokenize
from ..config import logger, model, tokenizer
from ..utils.db import insert_into_db

    
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
    instruction = "Represent the cybersecurity content:"
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