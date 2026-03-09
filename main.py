

import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from core.storage.storage import get_storage_backend
from core.router.router import app_router
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — nothing needed, storage initialises lazily on first use
    yield
    # shutdown — close the aiohttp session inside gcloud-aio-storage
    storage = get_storage_backend()
    await storage.close()
    print("GCS session closed.")

app = FastAPI(debug=True, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(app_router)

if __name__ == "__main__":
  uvicorn.run(app)