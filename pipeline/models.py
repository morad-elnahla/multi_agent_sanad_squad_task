"""Validated contracts used at every agent handoff."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Model(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Slot(Model):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]+$', max_length=64)
    type: str = Field(pattern=r'^[a-zA-Z0-9_-]+$')
    focus: str = Field(default='', max_length=200)

class Plan(Model):
    slots: list[Slot] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_ids(self):
        if len({s.id for s in self.slots}) != len(self.slots):
            raise ValueError('Slot IDs must be unique')
        return self

class KnowledgeFact(Model):
    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    text: str = Field(min_length=10)
    source_url: str

class Knowledge(Model):
    id: str
    name: str
    severity: Literal['Low', 'Medium', 'High', 'Critical']
    category: str
    description: str = Field(min_length=1)
    root_cause: str = Field(min_length=1)
    mitigation: str = Field(min_length=1)
    source_url: str
    severity_note: str
    facts: list[KnowledgeFact] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_facts(self):
        if len({f.id for f in self.facts}) != len(self.facts):
            raise ValueError("Fact IDs must be unique inside an entry")
        return self

class PostType(Model):
    name: str
    min_posts: int = Field(ge=1)
    max_posts: int = Field(ge=1)
    max_characters: int = Field(ge=1, le=280)
    writer: str

    @model_validator(mode='after')
    def valid_bounds(self):
        if self.min_posts > self.max_posts:
            raise ValueError('min_posts exceeds max_posts')
        return self

class TopicChoice(Model):
    kb_id: str
    reason: str

class Post(Model):
    text: str = Field(min_length=1)
    evidence_ids: list[str]

class Draft(Model):
    posts: list[Post] = Field(min_length=1)

class Support(Model):
    post_index: int = Field(ge=0)
    supported: bool
    reason: str

class Scores(Model):
    accuracy: int = Field(ge=0, le=5)
    usefulness: int = Field(ge=0, le=5)
    clarity: int = Field(ge=0, le=5)
    brand_fit: int = Field(ge=0, le=5)

class EvidenceQuote(Model):
    evidence_id: str
    quote: str = Field(min_length=1)

class ClaimCheck(Model):
    unit_id: str
    kind: Literal['factual', 'question', 'cta']
    supported: bool
    citations: list[EvidenceQuote]
    reason: str

class Judgment(Model):
    approve: bool
    scores: Scores
    claims: list[ClaimCheck] = Field(default_factory=list)
    support: list[Support]
    reasons: list[str]

class Visual(Model):
    prompt: str = Field(min_length=10)
    alt_text: str = Field(min_length=5)

class VisualConcept(Model):
    source_id: str
    layout: Literal['flow', 'barrier', 'cycle']
    symbol: Literal['arrows', 'gate', 'loop', 'shield']
