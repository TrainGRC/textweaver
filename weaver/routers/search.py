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
    
@router.post("/search/")
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
            metadata = result['metadata']
            # Extract the Title and Link or file information from the metadata
            link = metadata.get("URL", [])
            result_data = {}

            if metadata.get("Title", "unknown") != "unknown":
                result_data["Title"] = metadata.get("Title")
            if link:
                result_data["Link"] = link
            if metadata.get("PublicationDate", "unknown") != "unknown":
                result_data["Published"] = metadata.get("PublicationDate")
            if metadata.get("Author", "unknown") != "unknown":
                result_data["Author"] = metadata.get("Author")
            if metadata.get("Tags", "unknown") != "unknown":
                result_data["Tags"] = metadata.get("Tags")
            if metadata.get("Filename", "unknown") != "unknown":
                result_data["Filename"] = metadata.get("Filename")
            if metadata.get("text", "unknown") != "unknown":
                result_data["embedding_text"] = metadata.get("text")
            if metadata.get("doc_id", "unknown") != "unknown":
                result_data["DocumentID"] = metadata.get("doc_id")
            result_data["similarity_score"] = round(result['score'], 2)

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