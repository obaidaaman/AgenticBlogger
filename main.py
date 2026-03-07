
from core.agent import app
import uvicorn
from fastapi import FastAPI

from core.router.router import app_router

app = FastAPI(debug=True)

app.include_router(app_router)

if __name__ == "__main__":
  uvicorn.run(app)