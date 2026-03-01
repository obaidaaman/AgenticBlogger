from ..models.models import State, Plan, Tasks
from ...utils.llm_config import llm
from langchain_core.prompts import SystemMessage, HumanMessage
def orchestrator(state: State) ->dict:

    plan = llm.with_structured_output(Plan).invoke([
        SystemMessage(content=("Create a blog plan with 5-7 section on the following topic"
                               )
                               ),
        HumanMessage(content=f"Topic: {state['topic']}")
    ])

    return {"plan": plan}


