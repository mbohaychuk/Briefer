from fastapi import FastAPI

from app.middleware import ApiKeyMiddleware
from app.routers import health, ingestion

app = FastAPI(title="News Searcher ML Service")

app.add_middleware(ApiKeyMiddleware)
app.include_router(health.router)
app.include_router(ingestion.router)
