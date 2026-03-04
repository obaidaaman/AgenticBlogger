
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
  main(topic="Transformers in NLP and its recent trends in the Startup ecosystem")