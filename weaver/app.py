from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import run
import os
from .routers import search, upload, download
from .version import __version__
from .config import publish_sns_notification

try:
    import uvloop
    loop = "uvloop"
except ImportError:
    loop = "asyncio"

description = """
Textweaver helps you search your files and a treasure trove of cybersecurity information. 🚀

## Search

You can **search** for information in the database:
- leave the user_table parameter "false" to search our text corpus. "true" to search your own files.

## Upload

You can **upload** your own files to a private database:
- text (.txt) files
- pdf (.pdf) files
- audio (.mp3) files
- video (.mp4) files
- image (.jpg /.jpeg /.png / .tiff) files containing text
"""

app = FastAPI(    
    debug=False,
    title="Textweaver Search API",
    description=description,
    version=__version__,
    contact={
        "name": "Stinkbait",
        "url": "http://www.stinkbait.io/",
        "email": "support@traingrc.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://choosealicense.com/licenses/mit/",
    },
    docs_url="/docs",
    redoc_url="/redocs",
    openapi_tags=None
)

origins = [
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def start_app():
    host_ip = os.getenv("HOST_IP") or input("Enter host IP: ")
    port_num = int(os.getenv("PORT") or input("Enter port number: "))
    run(app, host=host_ip, port=port_num, loop=loop)  # Set max request body size to 600 MB for uvicorn

app.include_router(search.router)
app.include_router(upload.router)
app.include_router(download.router)

@app.get("/health")
def read_health():
    return {"status": "healthy"}

@app.on_event("startup")
def startup_event():
    publish_sns_notification("Stinkbait server has started.", "Stinkbait Startup")

@app.on_event("shutdown")
def shutdown_event():
    publish_sns_notification("Stinkbait server has shut down.", "Stinkbait Shutdown")