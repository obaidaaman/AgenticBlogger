from ..models.models import State, Plan
from utils.llm_config import llm
from langchain_core.messages import SystemMessage, HumanMessage
from utils.const import ORCH_SYSTEM
async def orchestrator(state: State) -> dict:

    mode = state["mode"]
    evidence = state["evidence"]
    feedback = state.get("feedback")
    previous_plan = state.get("plan")

    prompt = (
        f"Topic: {state['topic']}\n"
        f"Mode: {mode}\n\n"
        f"Evidence:\n{[e.model_dump() for e in evidence][:16]}\n\n"
        
    )

    if previous_plan and feedback:
        prompt += (
            "Previous Plan:\n"
            f"{previous_plan.model_dump()}\n\n"
            "User Feedback on the previous plan:\n"
            f"{feedback}\n\n"
            "Revise the plan accordingly."
        )

    

    plan = await llm.with_structured_output(Plan).ainvoke(
        [
            SystemMessage(content=ORCH_SYSTEM),
            HumanMessage(content=prompt)
        ]
    )

    return {"plan": plan}