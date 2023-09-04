from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, validator, Field
import os
import re
from typing import Optional
import time
from ..config import logger
from ..utils.db import vector_query
from ..utils.auth import get_auth

router = APIRouter()

# Define the model and the tokenizer
top_k = 5  # Default value; adjust as needed

class SearchRequest(BaseModel):
    query: str = Field(..., description="The search query string.")
    results_to_return: Optional[int] = Field(top_k, description="Number of results to return. Default is 5.")
    user_table: Optional[bool] = Field(False, description="Optional parameter to specify username for the table to search, must be an alphanumeric value or a valid email address.")
    
@router.post("/search")
def search(request: SearchRequest, claims: dict = Depends(get_auth)):
    """
    Endpoint to perform a search against the embeddings dataset.

    Takes a JSON object containing the search query and the number of results to return.

    Parameters:
        request (SearchRequest): JSON object containing 'query' (str), optional 'results_to_return' (int), and optional 'user_table' (bool).
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

    ## Uncomment the following lines to enable authentication
    username = claims.get('cognito:username') if request.user_table else None
    query = request.query
    results_to_return = request.results_to_return
    try:
        start_time = time.time()        
        top_results = vector_query(query, results_to_return, username)
        end_time = time.time()
        time_elapsed = round(end_time - start_time, 2)
        results = []
        for result in top_results['matches']:
            doc_id, metadata = result['id'], result['metadata']
            # Extract the Title and Link or file information from the metadata
            link = metadata.get("URL", [])

            result_data = {
                "Title": metadata.get("Title", "unknown"),
                "Link": link,
                "Published": metadata.get("PublicationDate", "unknown"),
                "Author": metadata.get("Author", "unknown"),
                "Tags": metadata.get("Tags", "unknown"),
                "Filename": metadata.get("Filename", "unknown"),
                "embedding_text": metadata.get("text", "unknown"),
                "DocumentID": doc_id if doc_id else "unknown",
                "similarity_score": round(result['score'], 2)
            }
            results.append(result_data)

        response = {
            "time_elapsed": time_elapsed,
            "results": results
        }

        return response

    except Exception as e:
        # Handle the exception as required
        return {"error": str(e)}
    finally:
        pass