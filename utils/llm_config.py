from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY") or "sk-placeholder-key-please-set-in-env"

llm = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=openai_api_key,
)
