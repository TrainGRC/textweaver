from setuptools import setup, find_packages

# Read the contents of the README file
def read_readme():
    try:
        with open('README.md', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "A FastAPI-based web server for working with LLMs, embedding models, and Pinecone Vector DB."


try:
    with open("weaver/version.py") as file:
        content = file.read()
        version = content.strip().split('=')[-1].replace('"', '').strip()
except Exception as e:
    version = "unknown"

setup(
    name='textweaver',
    version=version,
    author='Wes Ladd',
    author_email='wesladd@traingrc.com',
    keywords='textweaver, NLP, text-processing, machine-learning',
    description='A FastAPI-based web server for working with LLMs, embedding models, and Pinecone Vector DB.',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    url='https://github.com/TrainGRC/textweaver',
    packages=find_packages(),
    license='MIT',
    include_package_data=True,
    python_requires='>=3.9',  # Requires Python 3.9 or higher
    test_suite="tests",
    install_requires=[
        'fastapi',
        'uvicorn',
        'gunicorn',
        'ksuid',
        'pydantic',
        'numpy',
        'nltk',
        'transformers',
        'termcolor',
        'sentence-transformers',
        'starlette',
        'python-multipart',
        'whisper-ai',
        'moviepy',
        'mutagen',
        'PyPDF2',
        'uvloop',
        'boto3',
        'pydub',
        'jwt',
        'python-jose',
        'pinecone-client',
        'python-dotenv',
        'pdf2image',
        'python-magic',
        'httpx',
    ],
    entry_points={
        'console_scripts': [
            'textweaver=weaver.app:start_app',
            'textweaver-gunicorn=weaver.app:app',
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
