from fastapi import FastAPI
from uvicorn import run
import os
from .routers import search, upload
from .config import close_connection


app = FastAPI(    
    debug=False,
    title="Textweaver Search API",
    description="API for Text Weaver Document Search Engine",
    version="1.0.0",
    docs_url="/documentation",
    redoc_url="/redocumentation",
    openapi_tags=None
)

def start_app():
    host_ip = os.getenv("HOST_IP") or input("Enter host IP: ")
    port_num = int(os.getenv("PORT") or input("Enter port number: "))
    run(app, host=host_ip, port=port_num)

app.include_router(search.router)
app.include_router(upload.router)

# If needed, close the connection and cursor when the app is shut down
@app.on_event("shutdown")
def shutdown_event():
    close_connection()

if __name__ == "__main__":
    start_app()