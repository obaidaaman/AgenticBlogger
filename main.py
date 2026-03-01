from fastapi import FastAPI
from core.agent import app
import uvicorn


def main():
  out=  app.invoke({"topic" : "The future of AI in healthcare", "sections" : []})
  print(out)

if __name__ == "__main__":
  main()