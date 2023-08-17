from fastapi import APIRouter
from pydantic import BaseModel
from ..config import cursor, connection, model, tokenizer

import time
import json

router = APIRouter()

# Define the model and the tokenizer
instruction = "Represent the cybersecurity content:"
top_k = 5  # Default value; adjust as needed

class SearchRequest(BaseModel):
    query: str
    results_to_return: int = top_k  # Optional parameter with a default value

@router.post("/search")
def search(request: SearchRequest):
    """
    Endpoint to perform a search against the embeddings dataset.

    Takes a JSON object containing the search query and the number of results to return.

    Parameters:
        request (SearchRequest): JSON object containing 'query' (str) and optional 'results_to_return' (int).
                                 Example: {"query": "what is malware", "results_to_return": 10}

    Curl example:
        curl 'http://127.0.0.1:8000/search' \
             -X 'POST' \
             -H 'Content-Type: application/json' \
             --data '{"query": "what is malware", "results_to_return": 10}'

    Returns:
        dict: A dictionary containing the search results and the time taken to fetch them. 
        Example:
        {
            "time_elapsed": 0.2,
            "results": [
                {
                    "Title": "What is Malware?",
                    "Link": "http://example.com/malware",
                    "embedding_text": "text_body"
                },
                ...
            ]
        }
        
    Errors:
        If an error occurs during the execution, a JSON object containing an error message is returned.
        Example: {"error": "description of the error"}
    """
    query = request.query
    results_to_return = request.results_to_return
    query_vector = model.encode([[instruction, query]])[0].tolist()
    sql_query = """SELECT filename, metadata, embeddings_text, embeddings <-> %s::vector AS distance
                   FROM embeddings
                   ORDER BY distance
                   LIMIT %s"""

    try:
        start_time = time.time()
        cursor.execute(sql_query, (query_vector, results_to_return))
        top_results = cursor.fetchall()
        end_time = time.time()
        time_elapsed = round(end_time - start_time, 2)
        
        results = []
        for result in top_results:
            filename, metadata, embeddings_text, similarity_score = result
            json_header_line, text_body = embeddings_text.split('\n', 1)
            # Extract the Title and Link from the metadata
            links = metadata.get("links", [])
            for link_info in links:
                title = link_info.get("Title")
                link = link_info.get("Link") or link_info.get("link")
                results.append({
                    "Title": title,
                    "Link": link,
                    "Filename": filename,
                    "embedding_text": text_body,
                    "similarity_score": round(similarity_score, 2)
                })

        response = {
            "time_elapsed": time_elapsed,
            "results": results
        }

        return response

    except Exception as e:
        connection.rollback()
        # Handle the exception as required

        return {"error": str(e)}