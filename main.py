import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from core.router.router import app_router
from pymongo import AsyncMongoClient
import os
import logging
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    app.state.mongodb_client= AsyncMongoClient(os.getenv("MONGODB_URI"))

    app.state.database = app.state.mongodb_client.get_database("users")
    await app.state.database["users"].create_index("username", unique=True)
    app.state.logger = logger
    

    yield
    app.state.mongodb_client.close()
    


app = FastAPI(debug=True, lifespan=lifespan)

app.include_router(app_router)

if __name__ == "__main__":
  uvicorn.run(app)