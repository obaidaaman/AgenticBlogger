from langgraph.types import Send
from ..models.models import State, Plan
def fanout(state:State):
    return [ Send("worker", {"task" : task, "topic" : state["topic"], "plan" : state["plan"]})  for task in state['plan'].tasks]