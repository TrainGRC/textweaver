from ..config import get_connection, release_connection, logger
import numpy as np
import json

def check_table_exists(username: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()
    table_name = username.replace('@', '__').replace('.', '_')

    # Check if the table already exists
    cursor.execute(f"SELECT to_regclass('{table_name}');")
    exists = cursor.fetchone()[0]
    if exists:
        logger.warning(f"Table '{username}' exists.")
    else:
        logger.info(f"Table '{username}' does not exist.")
    
    release_connection(conn)
    return bool(exists)

def create_user_table(username):
    """
    Create a table in the database if it does not exist.

    Parameters:
        username (str): The username to be used as the table name. Must be alphanumeric.

    Returns:
        None

    Raises:
        HTTPException: If the username is not alphanumeric.

    Note:
        - This function checks whether a table with the given username already exists and creates it if not.
        - It prints messages to standard output for diagnostic purposes.
    """    
    if check_table_exists(username):
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    table_name = username.replace('@', '__').replace('.', '_')
    
    create_table_query = f"""
        CREATE TABLE {table_name} (
            filename VARCHAR NOT NULL,
            metadata JSON,
            embeddings VECTOR(768),
            embeddings_text VARCHAR 
        );
    """

    try:
        cursor.execute(create_table_query)
        logger.info(f"Table '{table_name}' created successfully.")
    except Exception as e:
        logger.info(f"An error occurred while creating the '{table_name}' table: {e}")
    conn.commit()
    release_connection(conn)

def insert_into_db(username, filename, metadata, embeddings, embeddings_text):
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
    table_name = username.replace('@', '__').replace('.', '_')

    # Convert the embeddings to a numpy array
    embeddings_array = np.array(embeddings)

    # If the array is 2-D with a single row, flatten it to 1-D
    if embeddings_array.ndim == 2 and embeddings_array.shape[0] == 1:
        embeddings_array = embeddings_array.flatten()

    # Convert the numpy array to a Python list
    embeddings_list = embeddings_array.tolist()
    insert_query = f"""
        INSERT INTO {table_name} (filename, metadata, embeddings, embeddings_text)
        VALUES (%s, %s, %s, %s);
    """

    connection = get_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(insert_query, (filename, json.dumps(metadata), embeddings_list, embeddings_text))
        logger.info(f"Record inserted successfully into '{table_name}' table.")
    except Exception as e:
        logger.info(f"An error occurred while inserting the record into the '{table_name}' table: {e}")
        raise

    connection.commit()
    release_connection(connection)