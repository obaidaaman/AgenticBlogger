import ast
import asyncio
import re
import sys
from typing import List, Tuple
from langchain_core.messages import SystemMessage, HumanMessage
from core.models.models import State
from utils.llm_config import llm


CODE_BLOCK_PATTERN = re.compile(r"```(?:python|py)[ \t]*\r?\n(.*?)```", re.DOTALL)


def extract_python_code(markdown_text: str) -> List[str]:
    return [match.strip() for match in CODE_BLOCK_PATTERN.findall(markdown_text) if match.strip()]


async def run_code_in_sandbox(code: str, timeout: float = 5.0) -> Tuple[bool, str]:
   
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError on line {e.lineno}: {e.msg}"

 
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        if proc.returncode != 0:
            error_msg = stderr.decode(errors="replace").strip()
        
            lines = error_msg.splitlines()
            cleaned = "\n".join(lines[-6:]) if len(lines) > 6 else error_msg
            return False, cleaned or "Process exited with non-zero status"

        return True, ""

    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return False, "Execution timed out (possible infinite loop)"
    except Exception as exc:
        return False, f"Runner error: {str(exc)}"


async def code_verifier_node(state: State) -> dict:
    sections = state.get("sections", [])
    if not sections:
        return {"code_errors": []}

    latest_sections = {}
    for task_id, md in sections:
        latest_sections[task_id] = md

    errors = []

    for task_id, md in latest_sections.items():
        snippets = extract_python_code(md)
        for snippet in snippets:
             
            if snippet.startswith("$") or snippet.startswith("# ..."):
                continue

            passed, error_msg = await run_code_in_sandbox(snippet)
            if not passed:
                errors.append({
                    "task_id": task_id,
                    "code": snippet,
                    "error": error_msg,
                })

    return {"code_errors": errors}


async def self_healing_node(state: State) -> dict:
    errors = state.get("code_errors", [])
    if not errors:
        return {}

   
    section_map = {}
    for task_id, md in state.get("sections", []):
        section_map[task_id] = md

    healed_sections = []

    
    for err in errors:
        task_id = err["task_id"]
        original_md = section_map.get(task_id, "")
        if not original_md:
            continue

        healing_prompt = (
            f"A Python code block in your section failed execution.\n\n"
            f"Failing Code:\n```python\n{err['code']}\n```\n\n"
            f"Runtime Error:\n{err['error']}\n\n"
            f"Original Section:\n{original_md}\n\n"
            f"Rewrite the section so the code runs without error. "
            f"Output the complete updated section markdown."
        )

        response = await llm.ainvoke([
            SystemMessage(content="You are a senior engineer fixing a runtime bug in technical blog code. Return only the revised section markdown."),
            HumanMessage(content=healing_prompt),
        ])

        healed_sections.append((task_id, response.content.strip()))

    retries = state.get("code_healing_retries") or 0
    return {
        "sections": healed_sections,
        "code_healing_retries": retries + 1,
    }


def route_after_code_check(state: State) -> str:
    errors = state.get("code_errors", [])
    retries = state.get("code_healing_retries") or 0

    # retry if there are bugs and under retry limit
    if errors and retries < 2:
        return "self_healing"
    return "reducer"
