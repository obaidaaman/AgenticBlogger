from langgraph.graph import StateGraph, START, END
from core.models.models import State
from .nodes.orchestrator import orchestrator
from .nodes.fanout import fanout
from .nodes.worker import worker_node
from .nodes.human_approval import human_review_node
from .nodes.router_node import router_node, route_next, route_after_review
from .nodes.research_node import research_node
from .nodes.generate_img import merge_content, decide_images, generate_and_place_images
from langgraph.checkpoint.memory import InMemorySaver


checkpointer= InMemorySaver()
# subgraph for image generation -> REDUCER
reducer_graph = StateGraph(State)
reducer_graph.add_node("merge_content", merge_content)
reducer_graph.add_node("decide_images", decide_images)
reducer_graph.add_node("generate_and_place_images", generate_and_place_images)
reducer_graph.add_edge(START, "merge_content")
reducer_graph.add_edge("merge_content", "decide_images")
reducer_graph.add_edge("decide_images", "generate_and_place_images")
reducer_graph.add_edge("generate_and_place_images", END)
reducer_subgraph = reducer_graph.compile()



g = StateGraph(State)
g.add_node("router", router_node)
g.add_node("research", research_node)
g.add_node("orchestrator", orchestrator)
g.add_node("worker", worker_node)
g.add_node("reducer", reducer_subgraph)
g.add_node("human_review", human_review_node)

g.add_edge(START, "router")
g.add_conditional_edges("router", route_next, {"research": "research", "orchestrator": "orchestrator"})
g.add_edge("research", "orchestrator")
g.add_edge("orchestrator","human_review")
g.add_conditional_edges("human_review", route_after_review, ["orchestrator", "worker"])
# g.add_conditional_edges("human", fanout, {
#     "worker" : "worker",
#     "orchestrator" : "orchestrator"
# })
g.add_edge("worker", "reducer")
g.add_edge("reducer", END)

app = g.compile(
    checkpointer=checkpointer,
    interrupt_before=["human_review"]
    )

