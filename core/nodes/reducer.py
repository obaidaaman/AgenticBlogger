from pathlib import Path
from ..models.models import State
import re
def reducer(state : State):
    plan = state["plan"]

    ordered_sections = [md for _, md in sorted(state["sections"], key=lambda x: x[0])]
    body = "\n\n".join(ordered_sections).strip()
    final_md = f"# {plan.blog_title}\n\n{body}\n"

    safe_title = re.sub(r'[<>:"/\\|?*]', "", plan.blog_title)
    safe_title = safe_title.replace(" ", "_")

    filename = f"{safe_title}.md"
    Path(filename).write_text(final_md, encoding="utf-8")

    return {"final": final_md}