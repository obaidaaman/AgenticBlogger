from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from utils.llm_config import llm
from core.nodes.code_sandbox import extract_python_code, run_code_in_sandbox


class RevisionDecision(BaseModel):
    target_task_id: int = Field(description="The section ID (1-based integer) that must be modified")
    section_title: str = Field(description="Title of the target section")
    specific_instructions: str = Field(description="Targeted instructions for rewriting only this section")


async def plan_revision(user_feedback: str, plan_tasks: List[Dict[str, Any]]) -> RevisionDecision:

    tasks_summary = "\n".join([
        f"Section {t.get('id')}: {t.get('title')} (Goal: {t.get('goal')})"
        for t in plan_tasks
    ])

    prompt = (
        f"User feedback: {user_feedback}\n\n"
        f"Available Sections:\n{tasks_summary}\n\n"
        f"Identify which section ID to edit and summarize the specific instructions."
    )

    decision = await llm.with_structured_output(RevisionDecision).ainvoke([
        SystemMessage(content="You are an editor. Match user revision requests to the single most relevant section ID."),
        HumanMessage(content=prompt),
    ])
    return decision


async def rewrite_section(old_content: str, instructions: str, blog_title: str) -> str:
    prompt = (
        f"Blog Title: {blog_title}\n\n"
        f"Current Section Content:\n{old_content}\n\n"
        f"Revision Instructions:\n{instructions}\n\n"
        f"Rewrite this section incorporating the instructions. "
        f"Maintain a technical developer tone and ensure code examples are complete. "
        f"Output ONLY the revised section Markdown."
    )

    response = await llm.ainvoke([
        SystemMessage(content="You are a senior engineer revising a technical blog section."),
        HumanMessage(content=prompt),
    ])
    revised_md = response.content.strip()


    snippets = extract_python_code(revised_md)
    for snippet in snippets:
        passed, error_msg = await run_code_in_sandbox(snippet)
        if not passed:

            healing_prompt = (
                f"Your code snippet failed runtime verification:\n```python\n{snippet}\n```\n"
                f"Error: {error_msg}\n\n"
                f"Please fix the code and return the corrected section."
            )
            healed = await llm.ainvoke([
                SystemMessage(content="Fix the code bug and return the complete revised section."),
                HumanMessage(content=healing_prompt),
            ])
            revised_md = healed.content.strip()
            break

    return revised_md
