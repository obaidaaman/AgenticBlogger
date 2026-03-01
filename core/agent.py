from langgraph.graph import StateGraph, START, END
from core.models.models import State
from .nodes.orchestrator import orchestrator
from .nodes.fanout import fanout
from .nodes.worker import worker
from .nodes.reducer import reducer
g = StateGraph(State)
g.add_node("orchestrator", orchestrator)
g.add_node("worker", worker)
g.add_node("reducer", reducer)

g.add_edge(START, "orchestrator")
g.add_conditional_edges("orchestrator", fanout,["worker"])
g.add_edge("worker", "reducer")
g.add_edge("reducer", END)

app = g.compile()

