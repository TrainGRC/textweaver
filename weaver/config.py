from psycopg2 import pool
import os
import getpass
import subprocess
import sys
import logging
import pinecone
import whisper
from nltk.tokenize import sent_tokenize
from transformers import BertTokenizer
from InstructorEmbedding import INSTRUCTOR
from termcolor import colored
import boto3


##############################################################################################
###                                  Logging Configuration                                 ###
##############################################################################################

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

##############################################################################################
###                                  Whisper AI Configuration                              ###
##############################################################################################

def install_ffmpeg():
    """
    Check if ffmpeg is installed on the host system.
    If not, it attempts to install it using the appropriate package manager.
    """

    # Check if ffmpeg is installed
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("ffmpeg is already installed.")
    except FileNotFoundError:
        logger.info("ffmpeg not found. Installing now...")

        # Determine the package manager (apt or yum) and install ffmpeg
        try:
            subprocess.run(["apt", "-v"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["apt-get", "update", "-y"], check=True)
            subprocess.run(["apt-get", "upgrade", "-y"], check=True)
            subprocess.run(["apt", "install", "ffmpeg", "-y"], check=True)
            logger.info("ffmpeg installed successfully using apt.")
        except FileNotFoundError:
            try:
                subprocess.run(["yum", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["sudo", "yum", "install", "ffmpeg"], check=True)
                logger.info("ffmpeg installed successfully using yum.")
            except FileNotFoundError:
                logger.error("Could not determine package manager. Please install ffmpeg manually.")
                sys.exit(1)

# Call the function at startup to ensure ffmpeg is installed
install_ffmpeg()
whisper_model = whisper.load_model("base")

##############################################################################################
###                                  DB Connection Configuration                           ###                    
##############################################################################################

# Pinecone connection parameters
PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY')
PINECONE_ENV = os.environ.get('PINECONE_ENVIRONMENT')
pinecone.init(
    api_key=PINECONE_API_KEY,
    environment=PINECONE_ENV
)

idx = pinecone.Index("stinkbait")

##############################################################################################
###                                     AWS Configuration                                  ###
##############################################################################################

# Get AWS credentials from environment variables
access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
default_region = os.getenv('AWS_DEFAULT_REGION')

# Check if the required environment variables are set
if not access_key_id or not secret_access_key or not default_region:
    raise EnvironmentError('AWS credentials not found in environment variables.')

# Create a boto3 session
aws_session = boto3.Session(
    aws_access_key_id=access_key_id,
    aws_secret_access_key=secret_access_key,
    region_name=default_region
)

# Create a boto3 Textract client using the session
textract_client = aws_session.client('textract')