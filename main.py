from fastapi import FastAPI
from core.agent import app
import uvicorn


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
  main(topic="Fundings in AI startups from 2024-2026")