
from typing import TypedDict, List, Annotated
import operator
from pydantic import BaseModel, Field


class Tasks(BaseModel):
    id: str
    title: str = Field(description="The title of the task")
    brief: str = Field(description="A brief description of the task")

class Plan(BaseModel):
    blog_title: str =Field(description="The title of the blog post")
    tasks:List[Tasks]

class State(TypedDict):
    topic: str
    plan: Plan
    # reducer: results from workers get concatenated automatically
    sections: Annotated[List[str], operator.add]
    final: str