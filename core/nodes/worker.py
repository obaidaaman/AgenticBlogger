from utils.llm_config import llm
from langchain_core.messages import SystemMessage, HumanMessage
def worker(payload : dict) ->dict :
    task = payload["task"]
    plan = payload["plan"]
    topic = payload["topic"]
    blog_title = plan.blog_title


    section_md = llm.invoke([
        SystemMessage(content="Write one clean Markdown section."),
            HumanMessage(
                content=(
                    f"Blog: {blog_title}\n"
                    f"Topic: {topic}\n\n"
                    f"Section: {task.title}\n"
                    f"Brief: {task.brief}\n\n"
                    "Return only the section content in Markdown."
                )
            )
    ]).content.strip()

    return {"sections": [section_md]}