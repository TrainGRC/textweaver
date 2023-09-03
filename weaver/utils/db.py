from ..config import model, idx, logger
import numpy as np
import json

    
def insert_user_record(username, filename, metadata, embeddings, embeddings_text):
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
    # Convert the embeddings to a numpy array
    embeddings_array = np.array(embeddings)

    # If the array is 2-D with a single row, flatten it to 1-D
    if embeddings_array.ndim == 2 and embeddings_array.shape[0] == 1:
        embeddings_array = embeddings_array.flatten()

    # Convert the numpy array to a Python list
    embeddings_list = embeddings_array.tolist()
    insert_query = f""""""

    try:
        #cursor.execute(insert_query, (filename, json.dumps(metadata), embeddings_list, embeddings_text))
        logger.info(f"Record inserted successfully into '{table_name}' table.")
    except Exception as e:
        logger.info(f"An error occurred while inserting the record into the '{table_name}' table: {e}")
        raise

    #connection.commit()
    #release_connection(connection)

def vector_query(query, results_to_return):
    try:
        instruction = "Represent the cybersecurity content:"
        query_vector = model.encode([[instruction, query]])[0].tolist()
        top_results = idx.query(query_vector, top_k=results_to_return, include_metadata=True)
        return top_results
    except Exception as e:
        logger.info(f"An error occurred while querying the database: {e}")
        raise