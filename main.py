
from core.agent import app
import uvicorn
from fastapi import FastAPI

from core.router.router import app_router

app = FastAPI(debug=True)

app.include_router(app_router)


def main(topic:str):
  out=  app.invoke({
            "topic": topic,
            "mode": "",
            "needs_research": False,
            "queries": [],
            "evidence": [],
            "plan": None,
            "sections": [],
            "final": "",
        })
  print(out)

if __name__ == "__main__":
  uvicorn.run(app)