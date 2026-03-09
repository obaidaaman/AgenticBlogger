"""
reducer.py — Reducer subgraph nodes (merge → decide_images → generate_and_place_images).

All file I/O now goes through StorageBackend; nothing touches the local filesystem.
The 'final' state key receives the rendered markdown string (with public GCS URLs).
The 'final_blog_url' key receives the GCS URL of the stored .md file.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from core.models.models import GlobalImagePlan, State
from core.storage.storage import get_storage_backend, slugify
from utils.const import DECIDE_IMAGES_SYSTEM
from utils.llm_config import llm


# ─────────────────────────────────────────────────────────────────────────────
# Node 1 — merge_content
# ─────────────────────────────────────────────────────────────────────────────

async def merge_content(state: State) -> dict[str, Any]:
    plan = state["plan"]
    ordered_sections = [
        md for _, md in sorted(state["sections"], key=lambda x: x[0])
    ]
    body = "\n\n".join(ordered_sections).strip()
    merged_md = f"# {plan.blog_title}\n\n{body}\n"
    return {"merged_md": merged_md}


# ─────────────────────────────────────────────────────────────────────────────
# Node 2 — decide_images
# ─────────────────────────────────────────────────────────────────────────────

async def decide_images(state: State) -> dict[str, Any]:
    plan = state["plan"]
    assert plan is not None

    planner = llm.with_structured_output(GlobalImagePlan)

    image_plan = await planner.ainvoke(
        [
            SystemMessage(content=DECIDE_IMAGES_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Topic: {state['topic']}\n\n"
                    "Insert placeholders + propose image prompts.\n\n"
                    f"{state['merged_md']}"
                )
            ),
        ]
    )

    return {
        "md_with_placeholders": image_plan.md_with_placeholders,
        "image_specs": [img.model_dump() for img in image_plan.images],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Node 3 — generate_and_place_images   ← all the storage logic lives here
# ─────────────────────────────────────────────────────────────────────────────

async def generate_and_place_images(state: State) -> dict[str, Any]:
    plan = state["plan"]
    assert plan is not None

    storage = get_storage_backend()

    md          = state.get("md_with_placeholders") or state["merged_md"]
    image_specs = state.get("image_specs") or []
    print("Reducer started")
    # ── Process each image spec ─────────────────────────────────────────────
    for spec in image_specs:
        placeholder  = spec["placeholder"]          # e.g. [[IMAGE_1]]
        raw_filename = spec["filename"]              # e.g. qkv_flow.png
        # Build a safe GCS blob name
        stem, _, ext = raw_filename.rpartition(".")
        safe_name    = f"{slugify(stem)}.{ext or 'png'}"
        blob_name    = f"images/{safe_name}"

        # ── Idempotency: skip generation if blob already exists in GCS ──────
        already_uploaded = await storage.exists(blob_name)

        if not already_uploaded:
            try:
                img_bytes = await _gemini_generate_image_bytes(spec["prompt"])
                image_url = await storage.upload_image(
                    filename=safe_name,
                    data=img_bytes,
                    content_type="image/png",
                )
                print("Image generated")
            except Exception as exc:
                # Replace placeholder with an informative block rather than
                # crashing the entire pipeline.
                fallback = (
                    f"> **[IMAGE GENERATION FAILED]** {spec.get('caption', '')}\n"
                    f">\n"
                    f"> **Alt:** {spec.get('alt', '')}\n"
                    f"> **Prompt:** {spec.get('prompt', '')}\n"
                    f"> **Error:** {exc}\n"
                )
                md = md.replace(placeholder, fallback)
                continue
        else:
            image_url = await storage.public_url(blob_name)

        # ── Swap placeholder for a markdown image with a public GCS URL ─────
        img_md = f"![{spec['alt']}]({image_url})\n*{spec['caption']}*"
        md = md.replace(placeholder, img_md)

    # ── Store the final markdown in GCS AND return it in state ──────────────
    print("Image loop done, starting markdown upload")
    safe_title   = slugify(plan.blog_title)
    md_filename  = f"{safe_title}.md"
    print(f"Uploading markdown: {md_filename}, size: {len(md)} chars")
    blog_url = await storage.upload_markdown(
        filename=md_filename,
        content=md,
    )

    return {
        "final": md,           
        "final_blog_url": blog_url,  
    }


# ─────────────────────────────────────────────────────────────────────────────
# Gemini image generation (unchanged logic, isolated here)
# ─────────────────────────────────────────────────────────────────────────────

async def _gemini_generate_image_bytes(prompt: str) -> bytes:
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY env var is not set.")

    client = genai.Client(api_key=api_key)

    resp = await client.aio.models.generate_content(
        # Fixed: was "gemini-2.5-flash-image" which does not exist
        model="gemini-2.5-flash-image",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_ONLY_HIGH",
                )
            ],
        ),
    )

    # Safely extract inline image bytes regardless of SDK version
    parts = getattr(resp, "parts", None)
    if not parts and getattr(resp, "candidates", None):
        try:
            parts = resp.candidates[0].content.parts
        except Exception:
            parts = None

    if not parts:
        raise RuntimeError(
            "Gemini returned no image content — check quota, safety filters, "
            "and that the model supports image generation."
        )

    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline and getattr(inline, "data", None):
            return inline.data  # type: ignore[return-value]

    raise RuntimeError("No inline image bytes found in Gemini response.")