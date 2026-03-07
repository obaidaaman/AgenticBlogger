from core.models.models import State
from langgraph.types import interrupt
def human_approval_node(state : State):
    user_decision = interrupt({
        "message" : "Please review the draft",
        "plan" : state["plan"]
    })
    return {"status": "approved" if user_decision.get("action") == "approve" else "rejected"}

