"""Grounded summary workflow schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class SummarySourceRequest(BaseModel):
    model_config=ConfigDict(extra="forbid")
    source_type: Literal["document","folder","note","conversation","pasted_text"]
    source_id: UUID|None=None
    title:str|None=Field(default=None,max_length=255)
    content:str|None=Field(default=None,max_length=200_000)

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

class SummaryConfig(BaseModel):
    summary_types:list[str]=["executive","detailed","key_points","action_items"]
    summary_lengths:list[str]=["brief","standard","detailed"]
    multi_document_modes:list[str]=["together","separate","compare"]
    max_sources:int=50
    max_custom_instructions:int=2000

class SaveSummaryNote(BaseModel):
    model_config=ConfigDict(extra="forbid")
    title:str|None=Field(default=None,max_length=255)

class SummaryFollowUp(BaseModel):
    model_config=ConfigDict(extra="forbid")
    question:str|None=Field(default=None,max_length=4000)
    mode:Literal["original_versions","latest_versions"]="original_versions"
