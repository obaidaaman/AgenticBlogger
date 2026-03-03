from ..models.models import State, Plan
from utils.llm_config import llm
from langchain_core.messages import SystemMessage, HumanMessage
from utils.const import ORCH_SYSTEM
def orchestrator(state: State) ->dict:

    mode = state['mode']
    evidence = state['evidence']
    plan = llm.with_structured_output(Plan).invoke([
        SystemMessage(content=(
                              ORCH_SYSTEM )
                               ),
        HumanMessage(content=(
           f"Topic: {state['topic']}\n"
                    f"Mode: {mode}\n\n"
                    f"Evidence (ONLY use for fresh claims; may be empty):\n"
                    f"{[e.model_dump() for e in evidence][:16]}"
        ))
    ])

    return {"plan": plan}


