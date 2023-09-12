import os
import subprocess
import platform
import sys
import logging
import pinecone
import whisper
import boto3
import nltk
from botocore.exceptions import ClientError
from typing import Optional
from transformers import BertTokenizer
from sentence_transformers import SentenceTransformer
from termcolor import colored
from dotenv import load_dotenv


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

##############################################################################################
###                          Environment Variables Configuration                           ###
##############################################################################################
# Load environment variables from .env file
env_file = False
try:
    env_file=load_dotenv('.env')
except Exception as e:
    logger.error(f"Error loading environment variables: {e}")
if env_file is False:
    logger.error("Environment file not found. Checking if environment variables are already loaded.")
    required_env_vars = [
        'HOST_IP',
        'PORT',
        'AWS_ACCESS_KEY_ID',
        'AWS_SECRET_ACCESS_KEY',
        'AWS_DEFAULT_REGION',
        'AWS_COGNITO_REGION',
        'AWS_USER_POOL_ID',
        'AWS_USER_POOL_CLIENT_ID',
        'SNS_TOPIC_NAME',
        'PINECONE_API_KEY',
        'PINECONE_ENVIRONMENT',
        'PINECONE_INDEX_NAME',
        'PINECONE_USER_INDEX_NAME',
        'MODEL_PATH'
    ]
    missing_env_vars = [var for var in required_env_vars if os.getenv(var) is None]
    if missing_env_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_env_vars)}. Please set them or create a .env file in the current working directory.")
        sys.exit(1)

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

def publish_sns_notification(info: str, subject: Optional[str] = None) -> Optional[str]:
    try:
        sns_client = aws_session.client('sns')
        topic_arn = f"arn:aws:sns:us-east-1:502534243523:{os.getenv('SNS_TOPIC_NAME')}"
        message = info
        publish_args = {"TopicArn": topic_arn, "Message": message}
        if subject is not None:
            publish_args["Subject"] = subject
        response = sns_client.publish(**publish_args)
        return response.get("MessageId")
    except ClientError as e:
        print(f"Failed to publish SNS message: {e}")
        return None

# Create a logging handler that publishes to SNS
class SNSNotificationHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        publish_sns_notification(log_entry, subject="Stinkbait Error")

sns_handler = SNSNotificationHandler()
sns_handler.setLevel(logging.ERROR)
logger.addHandler(sns_handler)
##############################################################################################
##                            Embedding Model and Tokenizer                                 ##
##############################################################################################
model = SentenceTransformer(f"{os.getenv('MODEL_PATH')}")
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

try:
    nltk.download('punkt')
    logger.info('Punkt dataset downloaded')
except Exception as e:
    logger.error(f"Error downloading NLTK punkt: {e}")
    sys.exit(1)
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
try:
    idx = pinecone.Index(os.getenv('PINECONE_INDEX_NAME'))
except Exception as e:
    logger.error(f"Error connecting to Pinecone: {e}")
    sys.exit(1)

try:
    user_idx = pinecone.Index(os.getenv('PINECONE_USER_INDEX_NAME'))
except Exception as e:
    logger.error(f"Error connecting to Pinecone: {e}")
    sys.exit(1)
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
                if os.geteuid() == 0:
                    subprocess.run(["yum", "install", "ffmpeg", "-y"], check=True)
                else:
                    subprocess.run(["sudo", "yum", "install", "ffmpeg", "-y"], check=True)
                logger.info("ffmpeg installed successfully using yum.")
            except FileNotFoundError:
                logger.error("Could not determine package manager. Please install ffmpeg manually.")
                sys.exit(1)

# Call the function at startup to ensure ffmpeg is installed
install_ffmpeg()
whisper_model = whisper.load_model("base")

##############################################################################################
###                                 Poppler Configuration                                  ###
##############################################################################################
def is_poppler_installed():
    try:
        result = subprocess.run(["pdftoppm", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return True
        else:
            return False
    except FileNotFoundError:
        return False

def install_poppler():
    os_type = platform.system()
    
    if os_type == "Darwin":  # macOS
        logger.info("Installing Poppler on macOS...")
        try:
            subprocess.run(["brew", "install", "poppler"], check=True)
        except subprocess.CalledProcessError:
            logger.info("Failed to install Poppler. Do you have Homebrew installed?")
            return False

    elif os_type == "Linux":
        logger.info("Installing Poppler on Linux...")
        # Detect package manager (apt, dnf, or zypper)
        try:
            subprocess.run(["apt-get", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.geteuid() == 0:
                subprocess.run(["apt-get", "update", "-y"], check=True)
                subprocess.run(["apt-get", "install", "poppler-utils", "-y"], check=True)
            else:
                subprocess.run(["sudo", "apt-get", "update", "-y"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "poppler-utils", "-y"], check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                subprocess.run(["dnf", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.geteuid() == 0:
                    subprocess.run(["dnf", "install", "poppler-utils", "-y"], check=True)
                else:
                    subprocess.run(["sudo", "dnf", "install", "poppler-utils", "-y"], check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                try:
                    subprocess.run(["zypper", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if os.geteuid() == 0:
                        subprocess.run(["zypper", "install", "poppler-tools", "-y"], check=True)
                    else:
                        subprocess.run(["sudo", "zypper", "install", "poppler-tools", "-y"], check=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    logger.info("Failed to detect a supported package manager (apt, dnf, zypper).")
                    return False
    else:
        logger.info("Unsupported operating system.")
        return False
    
    return True

# Run the functions directly upon import
if not is_poppler_installed():
    if install_poppler():
        logger.info("Poppler has been successfully installed.")
    else:
        logger.info("Failed to install Poppler.")
else:
    logger.info("Poppler is already installed. No action needed.")

##############################################################################################
###                                Libmagic Configuration                                  ###
##############################################################################################
def is_libmagic_installed():
    try:
        result = subprocess.run(["file", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            return True
        else:
            return False
    except FileNotFoundError:
        return False

def install_libmagic():
    os_type = platform.system()
    
    if os_type == "Darwin":  # macOS
        logger.info("Installing libmagic on macOS...")
        try:
            subprocess.run(["brew", "install", "libmagic"], check=True)
        except subprocess.CalledProcessError:
            logger.info("Failed to install libmagic. Do you have Homebrew installed?")
            return False

    elif os_type == "Linux":
        logger.info("Installing libmagic on Linux...")
        # Detect package manager (apt, dnf, or zypper)
        try:
            subprocess.run(["apt-get", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if os.geteuid() == 0:
                subprocess.run(["apt-get", "update", "-y"], check=True)
                subprocess.run(["apt-get", "install", "libmagic1", "-y"], check=True)
            else:
                subprocess.run(["sudo", "apt-get", "update", "-y"], check=True)
                subprocess.run(["sudo", "apt-get", "install", "libmagic1", "-y"], check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                subprocess.run(["dnf", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if os.geteuid() == 0:
                    subprocess.run(["dnf", "install", "file-libs", "-y"], check=True)
                else:
                    subprocess.run(["sudo", "dnf", "install", "file-libs", "-y"], check=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
                try:
                    subprocess.run(["zypper", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if os.geteuid() == 0:
                        subprocess.run(["zypper", "install", "file", "-y"], check=True)
                    else:
                        subprocess.run(["sudo", "zypper", "install", "file", "-y"], check=True)
                except (FileNotFoundError, subprocess.CalledProcessError):
                    logger.info("Failed to detect a supported package manager (apt, dnf, zypper).")
                    return False
    else:
        logger.info("Unsupported operating system.")
        return False
    
    return True

# Run the functions directly upon import
if not is_libmagic_installed():
    if install_libmagic():
        logger.info("libmagic has been successfully installed.")
    else:
        logger.info("Failed to install libmagic.")
else:
    logger.info("libmagic is already installed. No action needed.")