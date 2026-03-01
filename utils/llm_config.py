from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os
load_dotenv()
llm = ChatOpenAI(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_KEY")
)

