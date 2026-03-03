from langgraph.graph import StateGraph, START, END
from core.models.models import State
from .nodes.orchestrator import orchestrator
from .nodes.fanout import fanout
from .nodes.worker import worker_node
from .nodes.router_node import router_node, route_next
from .nodes.research_node import research_node

from .nodes.reducer import reducer
g = StateGraph(State)
g.add_node("router", router_node)
g.add_node("research", research_node)
g.add_node("orchestrator", orchestrator)
g.add_node("worker", worker_node)
g.add_node("reducer", reducer)

g.add_edge(START, "router")
g.add_conditional_edges("router", route_next, {"research": "research", "orchestrator": "orchestrator"})
g.add_edge("research", "orchestrator")

g.add_conditional_edges("orchestrator", fanout, ["worker"])
g.add_edge("worker", "reducer")
g.add_edge("reducer", END)

app = g.compile()
