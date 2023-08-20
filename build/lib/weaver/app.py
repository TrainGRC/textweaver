from fastapi import FastAPI
from uvicorn import run
from .routers import search, upload
from .config import close_connection


app = FastAPI()

def start_app():
    run(app, host="0.0.0.0", port=8000)

app.include_router(search.router)
app.include_router(upload.router)

# If needed, close the connection and cursor when the app is shut down
@app.on_event("shutdown")
def shutdown_event():
    close_connection()

if __name__ == "__main__":
    start_app()