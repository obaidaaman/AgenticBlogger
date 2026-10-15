import os
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from core.models.models import State
from .nodes.orchestrator import orchestrator
from .nodes.worker import worker_node
from .nodes.human_approval import human_review_node
from .nodes.router_node import router_node, route_next, route_after_review
from .nodes.research_node import research_node
from .nodes.code_sandbox import code_verifier_node, self_healing_node, route_after_code_check
from .nodes.generate_img import merge_content, decide_images, generate_and_place_images

# image generation and publishing subgraph
reducer_graph = StateGraph(State)
reducer_graph.add_node("merge_content", merge_content)
reducer_graph.add_node("decide_images", decide_images)
reducer_graph.add_node("generate_and_place_images", generate_and_place_images)

reducer_graph.add_edge(START, "merge_content")
reducer_graph.add_edge("merge_content", "decide_images")
reducer_graph.add_edge("decide_images", "generate_and_place_images")
reducer_graph.add_edge("generate_and_place_images", END)

reducer_subgraph = reducer_graph.compile()

# main blog orchestration workflow
g = StateGraph(State)
g.add_node("router", router_node)
g.add_node("research", research_node)
g.add_node("orchestrator", orchestrator)
g.add_node("worker", worker_node)
g.add_node("code_verifier", code_verifier_node)
g.add_node("self_healing", self_healing_node)
g.add_node("reducer", reducer_subgraph)
g.add_node("human_review", human_review_node)

g.add_edge(START, "router")
g.add_conditional_edges(
    "router",
    route_next,
    {"research": "research", "orchestrator": "orchestrator"},
)
g.add_edge("research", "orchestrator")
g.add_edge("orchestrator", "human_review")
g.add_conditional_edges("human_review", route_after_review, ["orchestrator", "worker"])

# parallel workers route into the code execution verifier
g.add_edge("worker", "code_verifier")

# self-healing loop: if errors, route to self_healing then re-verify; else proceed to reducer
g.add_conditional_edges(
    "code_verifier",
    route_after_code_check,
    {"self_healing": "self_healing", "reducer": "reducer"},
)
g.add_edge("self_healing", "code_verifier")
g.add_edge("reducer", END)

default_checkpointer = MemorySaver()


def build_graph(checkpointer=None):
    return g.compile(
        checkpointer=checkpointer or default_checkpointer,
        interrupt_before=["human_review"],
    )


app = build_graph(default_checkpointer)
