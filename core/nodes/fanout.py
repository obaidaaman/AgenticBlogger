from langgraph.types import Send
from ..models.models import State, Plan
def fanout(state:State):
    return [ Send("worker", {"task" : task.model_dump(), 
                             "topic" : state["topic"], 
                             "plan" : state["plan"].model_dump(),
                               "evidence": [e.model_dump() for e in state.get("evidence", [])]
                               }
                               )  for task in state["plan"].tasks]