from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from app.api.routes import router
from app.utils.version import BACKEND_VERSION

load_dotenv()

app = FastAPI(title="R2RML Demo API", version=BACKEND_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok"}
