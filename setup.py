from setuptools import setup, find_packages

# Read the contents of the README file
with open('README.md', encoding='utf-8') as f:
    long_description = f.read()

with open("weaver/version.py") as file:
    content = file.read()
    version = content.strip().split('=')[-1].replace('"', '').strip()

setup(
    name='textweaver',
    version=version,
    author='Wes Ladd',
    author_email='wesladd@traingrc.com',
    description='A FastAPI-based web server for working with LLMs, embedding models, and PostgresSQL.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/TrainGRC/textweaver',
    packages=find_packages(),
    include_package_data=True,
    python_requires='>=3.9',  # Requires Python 3.9 or higher
    install_requires=[
        'fastapi',
        'uvicorn',
        'ksuid',
        'numpy',
        'psycopg2-binary',
        'nltk',
        'transformers',
        'termcolor',
        'pydantic',
        'InstructorEmbedding',
        'sentence-transformers',
        'python-multipart',
        'whisper-ai',
        'moviepy',
        'mutagen',
        'PyPDF2',
        'uvloop',
        'boto3',
        'email-validator',
        'pydub',
        'jwt',
        'python-jose',
        'pinecone-client',
        'python-dotenv',
    ],
    entry_points={
        'console_scripts': [
            'textweaver=weaver.app:start_app',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.9',
    ],
)
