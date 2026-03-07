from ..models.models import State, RouterDecision
from utils.llm_config import llm
from core.nodes.fanout import fanout
from utils.const import ROUTER_SYSTEM
from langchain_core.messages import SystemMessage, HumanMessage
async def router_node(state: State) ->dict:
    topic = state['topic']
    decider = await llm.with_structured_output(RouterDecision).ainvoke([
        SystemMessage(content=ROUTER_SYSTEM),
        HumanMessage(content=f"Topic: {topic}"),
    ])


    return {
        "needs_research": decider.needs_research,
        "queries": decider.queries,
        "mode": decider.mode
    }


def route_next(state: State) -> str:
    if state['needs_research']:
        return "research"
    
    else:
        return "orchestrator"
    


def route_after_review(state:State):
    feedback = state.get("status")

    if feedback == "approve":
        return fanout(state)
    else:
        return "orchestrator"