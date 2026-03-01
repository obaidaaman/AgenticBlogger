from fastapi import FastAPI
from core.agent import app
import uvicorn


def main():
  out=  app.invoke({"topic" : "Write a blog on Self Attention", "sections" : []})
  print(out)

if __name__ == "__main__":
  main()