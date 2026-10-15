"""
controller.py — Controller logic for agent invocations and WebSocket lifecycle.
"""

import uuid
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from core.agent import app
from core.database import AsyncSessionLocal
from core.models.db_models import BlogPost
from core.models.response_model import ResponseModel
from core.nodes.editor import plan_revision, rewrite_section
from core.storage.storage import get_storage_backend, slugify
from sqlalchemy import update


def initial_state(topic: str) -> dict:
    return {
        "topic": topic,
        "mode": "",
        "needs_research": False,
        "queries": [],
        "evidence": [],
        "plan": None,
        "sections": [],
        "merged_md": "",
        "md_with_placeholders": "",
        "image_specs": [],
        "final": "",
        "status": "start",
        "notion_url": "",
        "code_errors": [],
        "code_healing_retries": 0,
    }


def response_controller(topic: str, config: dict):
    output = app.invoke(initial_state(topic), config=config)
    return ResponseModel(topic=topic, final=output.get("final", ""))


async def handle_agent_websocket(
    websocket: WebSocket,
    thread_id: str,
    user_info: Optional[dict] = None,
):
    config = {"configurable": {"thread_id": thread_id}}
    current_topic = ""

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "start":
                current_topic = data.get("topic", "")
                state = initial_state(topic=current_topic)
                await app.ainvoke(state, config=config)

                current_state = await app.aget_state(config)
                plan_pydantic = current_state.values.get("plan")

                await websocket.send_json({
                    "status": "plan_ready",
                    "plan": plan_pydantic.model_dump() if plan_pydantic else None,
                })

            elif action == "approve":
                await app.aupdate_state(config, {"status": "approve"})
                try:
                    await app.ainvoke(None, config=config)

                    final_state = await app.aget_state(config)
                    final_md = (
                        final_state.values.get("final_blog")
                        or final_state.values.get("final", "")
                    )
                    notion_url = final_state.values.get("notion_url", "")
                    blog_url = final_state.values.get("final_blog_url", "")
                    plan = final_state.values.get("plan")
                    blog_title = plan.blog_title if plan else current_topic

                   
                    if user_info and user_info.get("sub"):
                        try:
                            async with AsyncSessionLocal() as db:
                                post = BlogPost(
                                    user_id=uuid.UUID(user_info["sub"]),
                                    thread_id=thread_id,
                                    topic=current_topic or "AI Blog",
                                    title=blog_title,
                                    status="completed",
                                    markdown=final_md,
                                    blog_url=blog_url,
                                    notion_url=notion_url,
                                )
                                db.add(post)
                                await db.commit()
                        except Exception as db_err:
                            print(f"Notice: Could not persist blog to PostgreSQL: {db_err}")

                    await websocket.send_json({
                        "status": "completed",
                        "blog": final_md,
                        "blog_url": blog_url,
                        "notion_url": notion_url,
                    })
                except Exception as exc:
                    print(f"Generation error: {exc}")
                    await websocket.send_json({
                        "status": "error",
                        "message": str(exc),
                    })

            elif action == "decline":
                await app.aupdate_state(config, {"status": "decline"})
                await app.ainvoke(None, config=config)

                new_state = await app.aget_state(config)
                new_plan = new_state.values.get("plan")

                await websocket.send_json({
                    "status": "plan_ready",
                    "plan": new_plan.model_dump() if new_plan else None,
                })

            elif action == "revise":
                instruction = data.get("instruction", "").strip()
                if not instruction:
                    continue

                try:
                    current_state = await app.aget_state(config)
                    plan = current_state.values.get("plan")
                    sections = current_state.values.get("sections", [])

                    if not plan or not sections:
                        await websocket.send_json({
                            "status": "error",
                            "message": "No active article found in session to revise.",
                        })
                        continue

                   
                    decision = await plan_revision(
                        user_feedback=instruction,
                        plan_tasks=[t.model_dump() for t in plan.tasks],
                    )
                    target_id = decision.target_task_id

                  
                    latest_sections = {}
                    for tid, md in sections:
                        latest_sections[tid] = md
                    old_md = latest_sections.get(target_id, "")

                  
                    new_md = await rewrite_section(
                        old_content=old_md,
                        instructions=decision.specific_instructions,
                        blog_title=plan.blog_title,
                    )

                    
                    await app.aupdate_state(config, {"sections": [(target_id, new_md)]})

                    
                    latest_sections[target_id] = new_md
                    ordered = [latest_sections[tid] for tid in sorted(latest_sections.keys())]
                    final_md = f"# {plan.blog_title}\n\n" + "\n\n".join(ordered).strip() + "\n"

                   
                    storage = get_storage_backend()
                    safe_title = slugify(plan.blog_title)
                    blog_url = await storage.upload_markdown(
                        filename=f"{safe_title}.md",
                        content=final_md,
                    )

                   
                    if user_info and user_info.get("sub"):
                        try:
                            async with AsyncSessionLocal() as db:
                                await db.execute(
                                    update(BlogPost)
                                    .where(BlogPost.thread_id == thread_id)
                                    .values(markdown=final_md, blog_url=blog_url)
                                )
                                await db.commit()
                        except Exception as db_err:
                            print(f"Notice: Could not update blog in PostgreSQL: {db_err}")

                    await websocket.send_json({
                        "status": "completed",
                        "blog": final_md,
                        "blog_url": blog_url,
                        "notice": f"Section {target_id} ('{decision.section_title}') revised successfully!",
                    })

                except Exception as exc:
                    print(f"Revision error: {exc}")
                    await websocket.send_json({
                        "status": "error",
                        "message": f"Revision failed: {str(exc)}",
                    })

    except WebSocketDisconnect:
        print(f"WebSocket client disconnected for thread: {thread_id}")