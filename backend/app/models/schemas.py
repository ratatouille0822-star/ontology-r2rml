from typing import Any, List, Optional

from pydantic import BaseModel, Field


class IriItem(BaseModel):
    iri: str
    label: Optional[str] = None
    local_name: Optional[str] = None


class PropertyItem(BaseModel):
    iri: str
    label: Optional[str] = None
    local_name: Optional[str] = None
    domains: List[IriItem] = Field(default_factory=list)
    ranges: List[IriItem] = Field(default_factory=list)
    is_leaf: bool = True


class TableItem(BaseModel):
    name: str
    fields: List[str] = Field(default_factory=list)
    sample_rows: List[dict[str, Any]] = Field(default_factory=list)
    rows: List[dict[str, Any]] = Field(default_factory=list)


class MatchRequest(BaseModel):
    properties: List[PropertyItem]
    tables: List[TableItem]
    mode: str = Field(default="heuristic")
    threshold: float = Field(default=0.5)


class MatchItem(BaseModel):
    property_iri: str
    property_label: Optional[str] = None
    table_name: Optional[str] = None
    field: Optional[str] = None
    score: Optional[float] = None


class MatchResponse(BaseModel):
    matches: List[MatchItem]


class MappingItem(BaseModel):
    field: str
    property_iri: str
    table_name: Optional[str] = None


class AboxRequest(BaseModel):
    tables: List[TableItem]
    mapping: List[MappingItem]
    base_iri: str = Field(default="http://example.com/")


class R2RmlRequest(BaseModel):
    mapping: List[MappingItem]
    table_name: str = Field(default="data_table")
    base_iri: str = Field(default="http://example.com/")
