"""Grounded summary workflow schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class SummarySourceRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_type: Literal["document","note","conversation"]
    source_id: UUID

class SummaryCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    sources: list[SummarySourceRequest]=Field(min_length=1,max_length=50)
    summary_type: Literal["executive","detailed","key_points","action_items"]="executive"
    summary_length: Literal["brief","standard","detailed"]="standard"
    multi_document_mode: Literal["together","separate","compare"]="together"
    custom_instructions: str|None=Field(default=None,max_length=2000)
    title: str|None=Field(default=None,max_length=255)

class SummaryRecord(BaseModel):
    id:UUID; title:str; summary_type:str; summary_length:str; multi_document_mode:str; status:str
    content_markdown:str|None; citation_count:int; document_count:int; prompt_name:str; prompt_version:str
    created_at:datetime; completed_at:datetime|None; sources:list[dict]; citations:list[dict]; stale:bool=False

class SummaryList(BaseModel): items:list[SummaryRecord]

class SaveSummaryNote(BaseModel):
    model_config=ConfigDict(extra="forbid")
    title:str|None=Field(default=None,max_length=255)
