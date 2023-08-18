from psycopg2 import pool
from nltk.tokenize import sent_tokenize
from transformers import BertTokenizer
from InstructorEmbedding import INSTRUCTOR
import logging
from termcolor import colored
import os
import getpass

class ColoredConsoleHandler(logging.StreamHandler):
    COLORS = {
        'DEBUG': 'blue',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'magenta',
    }

    def emit(self, record):
        log_message = self.format(record)
        color = self.COLORS.get(record.levelname, 'white')
        print(colored(log_message, color))

# Create a logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


# Create the colored console handler
console_handler = ColoredConsoleHandler()
console_handler.setLevel(logging.INFO)  # Set level for the console handler

formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(console_handler)

# Model and Tokenizer
model = INSTRUCTOR('hkunlp/instructor-xl')
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

# Connection parameters
db_params = {
    'dbname': os.getenv('DB_NAME') or input('Enter your database name: '),
    'user': os.getenv('DB_USER') or input('Enter your database username: '),
    'password': os.getenv('DB_PASSWORD') or getpass.getpass('Enter your database password: '),
    'host': os.getenv('DB_HOST') or input('Enter your database hostname: '),
    'port': os.getenv('DB_PORT') or input('Enter your database port #: ')
}


# Connection pool parameters
connection_pool = pool.SimpleConnectionPool(1, 20, **db_params)

# Function to get a connection from the pool
def get_connection():
    return connection_pool.getconn()

# Function to release a connection back to the pool
def release_connection(connection):
    connection_pool.putconn(connection)

# Function to close all connections in the pool
def close_all_connections():
    connection_pool.closeall()

    
def close_connection():
    close_all_connections()