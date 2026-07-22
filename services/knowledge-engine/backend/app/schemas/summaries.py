"""Grounded summary workflow schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
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
    document_id:UUID|None=None; document_version_id:UUID|None=None; document_version_number:int|None=None
    structured_payload:dict[str,Any]|None=None; citation_snapshot:list[dict[str,Any]]=Field(default_factory=list)
    source_chunk_count:int=0; source_token_count:int=0; map_group_count:int=0
    model_name:str|None=None; language:str="en"; generation_config:dict[str,Any]=Field(default_factory=dict)
    provenance_hash:str|None=None; progress:dict[str,Any]=Field(default_factory=dict)
    started_at:datetime|None=None; updated_at:datetime|None=None; error_code:str|None=None; error_message:str|None=None
    retryable:bool=False
    suggested_questions:list[str]=Field(default_factory=list)

class SummaryList(BaseModel): items:list[SummaryRecord]

class SummaryConfig(BaseModel):
    summary_types:list[str]=["executive","detailed","key_points","action_items"]
    summary_lengths:list[str]=["brief","standard","detailed"]
    multi_document_modes:list[str]=["together","separate","compare"]
    max_sources:int=50
    max_custom_instructions:int=2000
    document_summary_types:list[str]=["overview","detailed","key_points","action_items"]
    document_default_type:str="overview"
    document_default_length:str="standard"

class DocumentAnalysisCreate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    summary_type:Literal["overview","detailed","key_points","action_items"]="overview"
    length:Literal["brief","standard","detailed"]="standard"
    force_regenerate:bool=False
    language:str=Field(default="en",min_length=2,max_length=16,pattern=r"^[A-Za-z]{2,8}(?:-[A-Za-z0-9]{2,8})?$")

class GroundedItem(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    text:str=Field(min_length=1,max_length=4000)
    citation_ids:list[str]=Field(min_length=1,max_length=64)

class DocumentMapOutput(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    section_summary:list[GroundedItem]=Field(default_factory=list)
    key_facts:list[GroundedItem]=Field(default_factory=list)
    dates:list[GroundedItem]=Field(default_factory=list)
    obligations:list[GroundedItem]=Field(default_factory=list)
    exceptions:list[GroundedItem]=Field(default_factory=list)
    risks:list[GroundedItem]=Field(default_factory=list)
    actions:list[GroundedItem]=Field(default_factory=list)
    definitions:list[GroundedItem]=Field(default_factory=list)
    coverage_gaps:list[str]=Field(default_factory=list,max_length=100)
    citation_ids:list[str]=Field(default_factory=list,max_length=512)

class AnalysisSection(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    heading:str=Field(min_length=1,max_length=160)
    items:list[GroundedItem]=Field(default_factory=list)

class DocumentFinalOutput(BaseModel):
    model_config=ConfigDict(extra="forbid",strict=True)
    title:str=Field(min_length=1,max_length=255)
    document_type:Literal["general","calendar","policy","standard","contract","report"]="general"
    sections:list[AnalysisSection]=Field(default_factory=list,max_length=40)
    key_findings:list[GroundedItem]=Field(default_factory=list)
    important_dates:list[GroundedItem]=Field(default_factory=list)
    requirements:list[GroundedItem]=Field(default_factory=list)
    action_items:list[GroundedItem]=Field(default_factory=list)
    coverage_gaps:list[str]=Field(default_factory=list,max_length=100)
    citation_ids:list[str]=Field(default_factory=list,max_length=512)
    suggested_questions:list[str]=Field(default_factory=list,max_length=8)

class DocumentAnalysisCreateResponse(BaseModel):
    disposition:Literal["reused","queued","running","completed"]
    summary:SummaryRecord

class DocumentAnalysisListResponse(BaseModel):
    document_id:UUID
    current_version_id:UUID
    summary_type:str
    length:str
    current:SummaryRecord|None=None
    previous:list[SummaryRecord]=Field(default_factory=list)

class SaveSummaryNote(BaseModel):
    model_config=ConfigDict(extra="forbid")
    title:str|None=Field(default=None,max_length=255)

class SummaryFollowUp(BaseModel):
    model_config=ConfigDict(extra="forbid")
    question:str|None=Field(default=None,max_length=4000)
    mode:Literal["original_versions","latest_versions"]="original_versions"
