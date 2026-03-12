
from typing import TypedDict, List, Annotated, Literal, Optional
import operator
from pydantic import BaseModel, Field


class Tasks(BaseModel):
    id: int
    title: str

    goal: str = Field(
        ...,
        description="One sentence describing what the reader should be able to do/understand after this section.",
    )
    bullets: List[str] = Field(
        ...,
        min_length=3,
        max_length=5,
        description="3–5 concrete, non-overlapping subpoints to cover in this section.",
    )
    target_words: int = Field(
        ...,
        description="Target word count for this section (120–450).",
    )
    section_type: Literal[
        "intro", "core", "examples", "checklist", "common_mistakes", "conclusion"
    ] = Field(
        ...,
        description="Use 'common_mistakes' exactly once in the plan.",
    )
    tags: List[str] = Field(default_factory=list)
    requires_research: bool
    requires_citations: bool
    requires_code:bool

class Plan(BaseModel):
    blog_title: str =Field(description="The title of the blog post")
    tasks:List[Tasks]
    audience:str
    tone:str
    blog_kind: Literal["explainer","tutorial", "news_roundup", "comparison", "system_design"]
    constraints: Optional[str] = Field(default_factory=list)

class EvidenceItem(BaseModel):
    title: str
    url:str
    published_date:Optional[str]
    snippet: Optional[str] = None
    source: Optional[str] = None


class RouterDecision(BaseModel):
    needs_research: bool
    mode: Literal["closed_book", "hybrid", "open_book"]
    queries: List[str] = Field(default_factory=list)


class State(TypedDict):
    topic: str
    # routing / research
    mode: str
    needs_research: bool
    queries: List[str] 
    evidence: List[EvidenceItem] 
    plan: Optional[Plan]
    # workers working.
    sections: Annotated[List[tuple[int, str]], operator.add]  # (task_id, section_md)
    merged_md: str
    md_with_placeholders: str
    image_specs: List[dict]
    final :str
    status : str
<<<<<<< Updated upstream

=======
    feedback: Optional[str]
    notion_url: str
>>>>>>> Stashed changes


# Multiple evidence cause worker will have 5-7 research topics, so each worker gives evidence and that evidence will be summed to list of evidence items for the final blog post

class EvidencePack(BaseModel):
    evidence : List[EvidenceItem] = Field(default_factory=list)


# FOR IMAGES GEMINI MODELL
class ImageSpec(BaseModel):
    placeholder: str = Field(..., description="e.g. [[IMAGE_1]]")
    filename: str = Field(..., description="Save under images/, e.g. qkv_flow.png")
    alt: str
    caption: str
    prompt: str = Field(..., description="Prompt to send to the image model.")
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"


class GlobalImagePlan(BaseModel):
    md_with_placeholders: str
    images: List[ImageSpec] = Field(default_factory=list)


class RequestBody(BaseModel):
    topic : str