from ..config import model, idx, user_idx, logger
import numpy as np
import json
    
def batch_insert_into_pinecone(file_key, username, records):
    try:
        user_idx.upsert(records, namespace=username)
        logger.info(f"Successfully batch inserted {len(records)} records")
    except Exception as e:
        with open("errors.txt", "a+") as error_file:  # Open "errors.txt" in append mode
            for file_key, *_ in records:
                error_file.write(f"{file_key}\n")
        logger.error(f"An error occurred while batch inserting: {e}")
        return str(e)

def vector_query(query, results_to_return, username=None):
    try:
        instruction = "query:"
        query_string = f"{instruction} {query}"
        query_vector = model.encode([query_string])[0].tolist()
        if username is not None:
            top_results = user_idx.query(query_vector, top_k=results_to_return, include_metadata=True, namespace=username)
            logger.info(f"Queried User Index for {username}")
        else:
            top_results = idx.query(query_vector, top_k=results_to_return, include_metadata=True)
        return top_results
    except Exception as e:
        logger.error(f"An error occurred while querying the database: {e}")
        return str(e)