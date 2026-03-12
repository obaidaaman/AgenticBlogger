"""
notion_publisher.py — Convert the blog's final Markdown into Notion blocks
and publish it as a new Notion page via the REST API.

Notion API version: 2025-09-03

Required env vars:
    NOTION_API_KEY       — your integration's Internal Integration Secret
    NOTION_PARENT_PAGE_ID — ID of the Notion page the blog will be created under
                            (share that page with your integration first)

Usage:
    from notion_publisher import publish_to_notion

    page_url = await publish_to_notion(
        title="How Transformers Work",
        markdown=md_string,
    )
    # returns the Notion page URL, e.g.
    # https://www.notion.so/How-Transformers-Work-<page_id>
"""

from __future__ import annotations

import os
import re
import html as html_module
from typing import Any
from dotenv import load_dotenv

import httpx  
load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

NOTION_VERSION = "2025-09-03"
NOTION_API     = "https://api.notion.com/v1"
# Notion rejects requests with more than 100 children at once
_BATCH_SIZE    = 95


async def publish_to_notion(
    title: str,
    markdown: str,
    parent_page_id: str | None = None,
    api_key: str | None = None,
) -> str:
    
    key       = api_key or os.environ["NOTION_API_KEY"]
    parent_id = parent_page_id or os.environ["NOTION_PARENT_PAGE_ID"]
    headers   = _headers(key)

    blocks = markdown_to_notion_blocks(markdown)

    first_batch = blocks[:_BATCH_SIZE]
    payload = {
        "parent":     {"page_id": parent_id},
        "properties": {
            "title": {
                "title": [{"type": "text", "text": {"content": title}}]
            }
        },
        "children": first_batch,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{NOTION_API}/pages",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        page = resp.json()
        page_id  = page["id"]
        page_url = page.get("url", f"https://www.notion.so/{page_id.replace('-', '')}")

     
        remaining = blocks[_BATCH_SIZE:]
        while remaining:
            batch     = remaining[:_BATCH_SIZE]
            remaining = remaining[_BATCH_SIZE:]

            patch_resp = await client.patch(
                f"{NOTION_API}/blocks/{page_id}/children",
                headers=headers,
                json={"children": batch},
            )
            patch_resp.raise_for_status()

    return page_url



def markdown_to_notion_blocks(md: str) -> list[dict[str, Any]]:
    """
    Parse Markdown and return a flat list of Notion block objects.

  """
    lines   = md.splitlines()
    blocks: list[dict[str, Any]] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            lang = line[3:].strip() or "plain text"
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(_code_block("\n".join(code_lines), lang))
            i += 1
            continue

    
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            tag   = f"heading_{level}"   
            blocks.append({
                "object": "block",
                "type":   tag,
                tag: {"rich_text": _parse_inline(m.group(2))},
            })
            i += 1
            continue

        if line.startswith(">"):
            bq_lines: list[str] = []
            while i < len(lines) and lines[i].startswith(">"):
                bq_lines.append(lines[i].lstrip("> ").strip())
                i += 1
            text = " ".join(bq_lines)
            blocks.append({
                "object": "block",
                "type":   "quote",
                "quote":  {"rich_text": _parse_inline(text)},
            })
            continue

        if re.match(r"^[-*_]{3,}$", line.strip()):
            blocks.append({"object": "block", "type": "divider", "divider": {}})
            i += 1
            continue

        if re.match(r"^[-*+]\s+", line):
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i]):
                text = re.sub(r"^[-*+]\s+", "", lines[i])
                blocks.append({
                    "object": "block",
                    "type":   "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": _parse_inline(text)},
                })
                i += 1
            continue


        if re.match(r"^\d+\.\s+", line):
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                text = re.sub(r"^\d+\.\s+", "", lines[i])
                blocks.append({
                    "object": "block",
                    "type":   "numbered_list_item",
                    "numbered_list_item": {"rich_text": _parse_inline(text)},
                })
                i += 1
            continue

    
        img_m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line)
        if img_m:
            alt = img_m.group(1)
            url = img_m.group(2)
            blocks.append({
                "object": "block",
                "type":   "image",
                "image":  {
                    "type":     "external",
                    "external": {"url": url},
                    "caption":  [],   
                },
            })
   
            if i + 1 < len(lines):
                cap_m = re.match(r"^\*([^*]+)\*$", lines[i + 1].strip())
                if cap_m:
                    blocks[-1]["image"]["caption"] = _parse_inline(cap_m.group(1))
                    i += 1
            i += 1
            continue

        if not line.strip():
            i += 1
            continue


        para_lines: list[str] = []
        while i < len(lines):
            l = lines[i]
            if (
                not l.strip()
                or l.startswith("#")
                or l.startswith(">")
                or l.startswith("```")
                or re.match(r"^[-*+]\s+", l)
                or re.match(r"^\d+\.\s+", l)
                or re.match(r"^[-*_]{3,}$", l.strip())
                or re.match(r"^!\[", l)
            ):
                break
            para_lines.append(l)
            i += 1

        if para_lines:
            text = " ".join(para_lines)
            blocks.append({
                "object":    "block",
                "type":      "paragraph",
                "paragraph": {"rich_text": _parse_inline(text)},
            })

    return blocks


def _parse_inline(text: str) -> list[dict[str, Any]]:
    """
    Split `text` into a list of Notion rich_text objects, handling:
        **bold**, *italic*, `code`, [link](url), plain text.
    Returns [] for empty strings (Notion rejects empty rich_text in some blocks).
    """
    if not text.strip():
        return [_rt("")]


    pattern = re.compile(
        r"(\*\*\*(.+?)\*\*\*)"    
        r"|(\*\*(.+?)\*\*)"        
        r"|(\*(.+?)\*)"            
        r"|(`([^`]+)`)"            
        r"|(\[([^\]]+)\]\(([^)]+)\))"  
    )

    result: list[dict[str, Any]] = []
    last = 0

    for m in pattern.finditer(text):
       
        if m.start() > last:
            result.append(_rt(text[last:m.start()]))

        if m.group(1):   
            result.append(_rt(m.group(2), bold=True, italic=True))
        elif m.group(3): 
            result.append(_rt(m.group(4), bold=True))
        elif m.group(5): 
            result.append(_rt(m.group(6), italic=True))
        elif m.group(7): 
            result.append(_rt(m.group(8), code=True))
        elif m.group(9): 
            result.append(_rt(m.group(10), url=m.group(11)))

        last = m.end()

   
    if last < len(text):
        result.append(_rt(text[last:]))

    return result or [_rt("")]


def _rt(
    content: str,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    url: str | None = None,
) -> dict[str, Any]:
    """Build a single Notion rich_text object."""
    obj: dict[str, Any] = {
        "type": "text",
        "text": {"content": content, "link": {"url": url} if url else None},
        "annotations": {
            "bold":          bold,
            "italic":        italic,
            "strikethrough": False,
            "underline":     False,
            "code":          code,
            "color":         "default",
        },
    }
    return obj


def _code_block(code: str, language: str) -> dict[str, Any]:
    """
    Notion code block.
    language must be one of Notion's accepted values; unknown langs fall back
    to 'plain text' which Notion always accepts.
    """
   
    _NOTION_LANGS = {
        "python", "javascript", "typescript", "bash", "shell", "json",
        "yaml", "html", "css", "sql", "java", "kotlin", "swift", "go",
        "rust", "c", "cpp", "c++", "csharp", "c#", "ruby", "php",
        "scala", "markdown", "dockerfile", "plain text",
    }
    safe_lang = language.lower() if language.lower() in _NOTION_LANGS else "plain text"
    return {
        "object": "block",
        "type":   "code",
        "code":   {
            "rich_text": [_rt(code)],
            "language":  safe_lang,
        },
    }


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization":  f"Bearer {api_key}",
        "Content-Type":   "application/json",
        "Notion-Version": NOTION_VERSION,
    }