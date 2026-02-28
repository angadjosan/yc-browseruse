"""Compliance Change Radar — FastAPI application."""
from pathlib import Path

from dotenv import load_dotenv

# Load .env from backend/ or project root (so "cd backend && uvicorn" finds either)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # backend/.env
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")  # project root .env

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Shutdown: close pools, etc.
    pass


app = FastAPI(
    title="Compliance Change Radar API",
    description="Describe your product; we watch every regulation and vendor policy that affects you and ticket your team when something changes.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {"service": "Compliance Change Radar API", "docs": "/docs"}
