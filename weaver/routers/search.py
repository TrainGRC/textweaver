from fastapi import APIRouter
from pydantic import BaseModel
from ..config import get_connection, release_connection, model, tokenizer

import time
import json

router = APIRouter()

# Define the model and the tokenizer
instruction = "Represent the cybersecurity content:"
top_k = 5  # Default value; adjust as needed

class SearchRequest(BaseModel):
    query: str
    results_to_return: int = top_k  # Optional parameter with a default value
    search_type: str = "euclidean"  # New optional parameter with default value
    probes: int = 10  # Optional parameter for number of probes, defaults to 1
    workers: int = 1  # Optional parameter for number of workers, defaults to 1


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
             --data '{"query": "string", "results_to_return": 5, "search_type": "euclidean", "probes": 100}'

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
    connection = get_connection()
    cursor = connection.cursor()
    probes = request.probes
    query = request.query
    workers = request.workers
    results_to_return = request.results_to_return
    query_vector = model.encode([[instruction, query]])[0].tolist()
    search_type = request.search_type
    
    # Validate and get the corresponding operator
    operator_mapping = {
        "euclidean": "<->",
        "inner_product": "<#>",
        "cosine": "<=>"
    }
    operator = operator_mapping.get(search_type, "<->")  # Default to euclidean if an invalid value is provided
    sql_query = f"""SELECT filename, metadata, embeddings_text, embeddings {operator} %s::vector AS distance
                   FROM embeddings
                   ORDER BY distance
                   LIMIT %s"""

    try:
        start_time = time.time()        
        cursor.execute("BEGIN;")
        cursor.execute(f"SET LOCAL ivfflat.probes = {probes};")
        cursor.execute(f"SET LOCAL max_parallel_workers_per_gather = {workers};")
        cursor.execute(sql_query, (query_vector, results_to_return))
        top_results = cursor.fetchall()
        end_time = time.time()
        time_elapsed = round(end_time - start_time, 2)
        cursor.execute("COMMIT;")
        results = []
        for result in top_results:
            filename, metadata, embeddings_text, similarity_score = result
            json_header_line, text_body = embeddings_text.split('\n', 1)
            if search_type == "cosine":
                similarity_score = 1 - similarity_score
            elif search_type == "inner_product":
                similarity_score = abs(similarity_score)
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
    finally:
        release_connection(connection)