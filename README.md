# AgenticBlogger




# Agentic Blogger

An **Agentic AI blogging pipeline** built using **LangGraph, FastAPI, and structured LLM outputs**.
The system generates complete blog posts from a topic by orchestrating multiple AI agents including routing, research, planning, parallel section generation, and image generation.

The workflow includes **human-in-the-loop approval** before content generation, ensuring control over the final structure of the article.

---

# Architecture Overview

The system follows an **agent orchestration pipeline** implemented with **LangGraph**.
<img width="176" height="771" alt="image" src="https://github.com/user-attachments/assets/73e6ce84-f950-4864-a885-3c46a2af738e" />
High-level flow:

Topic → Router → Research (optional) → Planner → Human Review → Fanout Workers → Merge → Image Generation → Final Blog

---

# Core Features

### Agentic Workflow

The pipeline is composed of multiple agents responsible for different stages of blog creation.

Agents include:

* **Router Agent**
* **Research Agent**
* **Planning Agent**
* **Worker Agents**
* **Merge Agent**
* **Image Generation Agent**

Each stage updates a shared **LangGraph state object**.

---

### Human-in-the-loop Approval

Before article generation begins, the system sends a **structured blog plan** to the client via WebSocket.

The user can:

* Approve the plan
* Decline and request a new plan

This enables editorial control before expensive generation begins.

---

### Structured LLM Outputs

All LLM outputs are validated using **Pydantic schemas**.

Examples include:

* RouterDecision
* Plan
* Tasks
* EvidenceItem
* ImageSpec

This prevents hallucinated structures and guarantees schema correctness.

---

# System Components

## Router Node

Determines whether the topic requires external research.

Outputs:

* needs_research
* queries
* generation mode

Possible modes:

closed_book
hybrid
open_book

---

## Research Node

Executed only if `needs_research=True`.

The system:

1. Generates search queries
2. Retrieves sources
3. Stores structured evidence

Evidence structure:

* title
* url
* snippet
* published_date

---

## Planning Agent

Creates a **structured blog outline**.

The plan includes:

* Blog title
* Audience
* Tone
* Blog type
* Section tasks

Each section task defines:

* title
* goal
* bullet points
* target word count
* section type
* tags
* research requirements
* code requirements

---

## Section Workers (Fanout)

After plan approval:

1. Each section becomes a **worker task**
2. Workers generate content in parallel
3. Each worker produces markdown

Output format:

```
(task_id, section_markdown)
```

Results are accumulated using:

```
Annotated[List[tuple[int,str]], operator.add]
```

---

## Merge Node

Combines generated sections into a single markdown document.

Outputs:

* merged_md
* md_with_placeholders

---

## Image Planning Agent

Analyzes the markdown and inserts placeholders such as:

```
[[IMAGE_1]]
```

Image specifications include:

* filename
* caption
* alt text
* generation prompt
* size
* quality

Images are generated later using **Gemini image models**.

---

# WebSocket Workflow

The system uses **FastAPI WebSockets** for real-time agent interaction.

## Client Actions

### Start Generation

Client sends:

```json
{
  "action": "start",
  "topic": "LangGraph Architecture"
}
```

Server:

1. Initializes graph state
2. Runs router + planner
3. Returns the generated plan

Response:

```json
{
  "status": "plan_ready",
  "plan": {...}
}
```

---

### Approve Plan

Client sends:

```json
{
  "action": "approve"
}
```

Server:

1. Updates state
2. Runs fanout workers
3. Generates blog

Response:

```json
{
  "status": "completed",
  "blog": "..."
}
```

---

### Decline Plan

Client sends:

```json
{
  "action": "decline"
}
```

Server:

1. Returns control to orchestrator
2. Generates a new plan

---

# State Management

All pipeline data is stored in a shared LangGraph state.

```
State
```

Fields include:

topic
mode
needs_research
queries
evidence
plan
sections
merged_md
image_specs
final
status

This allows nodes to read/write intermediate outputs.

---

# Project Structure

Example layout:

```
core/
 ├── agent.py
 ├── nodes/
 │   ├── router.py
 │   ├── orchestrator.py
 │   ├── research.py
 │   ├── fanout.py
 │   ├── workers.py
 │   └── merge.py
 │
 ├── models/
 │   ├── models.py
 │   └── response_model.py
 │
 ├── websocket/
 │   └── handler.py

utils/
 ├── llm_config.py
 └── const.py

main.py
```

---

# Tech Stack

| Component             | Technology            |
| --------------------- | --------------------- |
| API                   | FastAPI               |
| Agent orchestration   | LangGraph             |
| LLM interface         | LangChain             |
| Structured validation | Pydantic              |
| Communication         | WebSockets            |
| Image generation      | Gemini                |
| Research              | External search tools |

---

# Example Use Case

Input:

```
Topic: "Vector Databases vs Traditional Databases"
```

Pipeline execution:

Router → Research → Plan → User Approval → Worker Generation → Merge → Image Planning → Final Blog

Output:

A complete article including:

* structured sections
* technical explanations
* code examples
* images
* citations

---

# Future Improvements

Potential enhancements:

* Streaming token responses
* Persistent conversation memory
* citation verification
* SEO optimization agent
* automatic diagram generation
* markdown → HTML rendering
* multi-language blog generation

---

# Why This Project Exists

Most AI writing tools generate **flat text** with little structure.

This system instead implements a **true agentic pipeline**:

* reasoning before generation
* planning before writing
* human approval
* parallel section workers
* structured outputs

The result is **more controllable and higher quality AI-generated content**.

---

# License

MIT License
