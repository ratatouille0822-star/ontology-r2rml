from typing import Any, List, Optional

from pydantic import BaseModel, Field


class PropertyItem(BaseModel):
    iri: str
    label: Optional[str] = None
    local_name: Optional[str] = None


class MatchRequest(BaseModel):
    fields: List[str]
    properties: List[PropertyItem]
    mode: str = Field(default="heuristic")


class MatchItem(BaseModel):
    field: str
    property_iri: Optional[str] = None
    property_label: Optional[str] = None
    score: Optional[float] = None


class MatchResponse(BaseModel):
    matches: List[MatchItem]


class MappingItem(BaseModel):
    field: str
    property_iri: str


class AboxRequest(BaseModel):
    rows: List[dict[str, Any]]
    mapping: List[MappingItem]
    base_iri: str = Field(default="http://example.com/")


class R2RmlRequest(BaseModel):
    mapping: List[MappingItem]
    table_name: str = Field(default="data_table")
    base_iri: str = Field(default="http://example.com/")
