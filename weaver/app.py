from fastapi import FastAPI
from uvicorn import run
import os
from .routers import search, upload
from .config import close_connection
from .version import __version__

try:
    import uvloop
    loop = "uvloop"
except ImportError:
    loop = "asyncio"

description = """
Textweaver helps you search your files and a treasure trove of cybersecurity information. 🚀

## Search

You can **search** for information in the database:
- leave the user_table parameter off to search our text corpus.
- add the user_table parameter to search your own data.

## Upload

You can **upload** your own files to a private database:
- text files
- pdf files
- audio files
- video files
"""

app = FastAPI(    
    debug=False,
    title="Textweaver Search API",
    description=description,
    version=__version__,
    contact={
        "name": "Train GRC Inc.",
        "url": "http://www.traingrc.com/",
        "email": "support@traingrc.com",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
    },
    docs_url="/documentation",
    redoc_url="/redocumentation",
    openapi_tags=None
)

def start_app():
    host_ip = os.getenv("HOST_IP") or input("Enter host IP: ")
    port_num = int(os.getenv("PORT") or input("Enter port number: "))
    run(app, host=host_ip, port=port_num, loop=loop)

app.include_router(search.router)
app.include_router(upload.router)

# If needed, close the connection and cursor when the app is shut down
@app.on_event("shutdown")
def shutdown_event():
    close_connection()

if __name__ == "__main__":
    start_app()