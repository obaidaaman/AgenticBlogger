"""
main.py — FastAPI application entry point with PostgreSQL & Supabase integration.
"""

import os
import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from core.router.router import app_router
from core.database import init_db, close_db
from core.storage.storage import get_storage_backend
from core.agent import build_graph, default_checkpointer

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing AgenticBlogger services...")
    app.state.logger = logger

    # 1. Initialize PostgreSQL database tables
    try:
        await init_db()
        logger.info("PostgreSQL database tables initialized successfully.")
    except Exception as e:
        logger.warning(
            f"PostgreSQL connection failed: {e}. "
            "Ensure DATABASE_URL is configured in your .env file."
        )

    # 2. Checkpointer setup:
    postgres_checkpointer_uri = os.getenv("POSTGRES_CHECKPOINTER_URI") or os.getenv("DATABASE_URL")
    pool = None
    if postgres_checkpointer_uri:
        clean_uri = postgres_checkpointer_uri.replace("postgresql+asyncpg://", "postgresql://")
        try:
            from psycopg_pool import AsyncConnectionPool
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            # prepare_threshold=None disables prepared statements for Supabase PgBouncer (port 6543)
            pool = AsyncConnectionPool(
                conninfo=clean_uri,
                max_size=10,
                kwargs={"prepare_threshold": None},
                open=False,
            )
            await pool.open()
            pg_checkpointer = AsyncPostgresSaver(pool)
            await pg_checkpointer.setup()
            app.state.agent = build_graph(pg_checkpointer)
            logger.info("LangGraph AsyncPostgresSaver initialized with PgBouncer support.")
        except Exception as e:
            logger.warning(f"Could not initialize AsyncPostgresSaver ({e}), falling back to in-memory checkpointer.")
            app.state.agent = build_graph(default_checkpointer)
    else:
        app.state.agent = build_graph(default_checkpointer)

    yield

    # Shutdown: release resources
    logger.info("Shutting down AgenticBlogger services...")
    if pool:
        await pool.close()
    storage = get_storage_backend()
    await storage.close()
    await close_db()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="AgenticBlogger API",
    description="Multi-agent technical blog generator with LangGraph, PostgreSQL, and Supabase",
    version="1.0.0",
    lifespan=lifespan,
)

from fastapi.responses import FileResponse

origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "null",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"^https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(app_router)


@app.get("/", include_in_schema=False)
async def serve_ui():
   
    return FileResponse("test_ui.html")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)