"""``pipeline.yaml`` manifest models.

The pipeline manifest describes how a source becomes graph objects:
parsing, extraction, mapping, and the destination graph database.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator

from graphflow_core.manifests.common import (
    STRICT_MODEL_CONFIG,
    ManifestVersion,
    is_pascal_case,
    is_screaming_snake_case,
    is_snake_case,
)

ExtractionMode = Literal["none", "fast", "accurate", "hybrid"]
DestinationType = Literal["neo4j"]
WriteMode = Literal["merge", "create"]


class ExtractionSpec(BaseModel):
    """How candidate graph entities are produced from records or text."""

    model_config = STRICT_MODEL_CONFIG

    mode: ExtractionMode


class NodeKeyMapping(BaseModel):
    """How to populate a node's key property from source fields."""

    model_config = STRICT_MODEL_CONFIG

    from_field: str

    @field_validator("from_field")
    @classmethod
    def _from_field_is_snake_case(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(f"mapping key.from_field '{value}' must be snake_case")
        return value


class NodeMapping(BaseModel):
    """Map records from a source to nodes of one ontology label."""

    model_config = STRICT_MODEL_CONFIG

    label: str
    source: str = Field(description="Source selector, e.g. 'rows[]'")
    key: NodeKeyMapping
    properties: dict[str, str] = Field(default_factory=dict)

    @field_validator("label")
    @classmethod
    def _label_is_pascal_case(cls, value: str) -> str:
        if not is_pascal_case(value):
            raise ValueError(f"mapping node label '{value}' must be PascalCase")
        return value

    @field_validator("properties")
    @classmethod
    def _property_names_are_snake_case(cls, value: dict[str, str]) -> dict[str, str]:
        for name, source_field in value.items():
            if not is_snake_case(name):
                raise ValueError(f"mapping property name '{name}' must be snake_case")
            if not is_snake_case(source_field):
                raise ValueError(
                    f"mapping property '{name}' source field '{source_field}' must be snake_case"
                )
        return value


class RelationshipEndpointMapping(BaseModel):
    """How to identify a relationship endpoint from source fields."""

    model_config = STRICT_MODEL_CONFIG

    label: str
    from_field: str

    @field_validator("label")
    @classmethod
    def _label_is_pascal_case(cls, value: str) -> str:
        if not is_pascal_case(value):
            raise ValueError(f"relationship endpoint label '{value}' must be PascalCase")
        return value

    @field_validator("from_field")
    @classmethod
    def _from_field_is_snake_case(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(f"relationship endpoint from_field '{value}' must be snake_case")
        return value


class RelationshipMapping(BaseModel):
    """Map records to relationships of one ontology type."""

    model_config = STRICT_MODEL_CONFIG

    type: str
    source: str
    from_node: RelationshipEndpointMapping = Field(alias="from")
    to_node: RelationshipEndpointMapping = Field(alias="to")
    properties: dict[str, str] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _type_is_screaming_snake(cls, value: str) -> str:
        if not is_screaming_snake_case(value):
            raise ValueError(f"relationship type '{value}' must be SCREAMING_SNAKE_CASE")
        return value


class MappingSpec(BaseModel):
    """Mapping rules from source records to graph objects."""

    model_config = STRICT_MODEL_CONFIG

    nodes: list[NodeMapping] = Field(default_factory=list)
    relationships: list[RelationshipMapping] = Field(default_factory=list)


class DestinationSpec(BaseModel):
    """Where the pipeline writes its graph objects."""

    model_config = STRICT_MODEL_CONFIG

    type: DestinationType
    connection_ref: str
    write_mode: WriteMode = "merge"
    batch_size: int = Field(default=1000, gt=0)

    @field_validator("connection_ref")
    @classmethod
    def _connection_ref_is_snake_case(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(f"destination.connection_ref '{value}' must be snake_case")
        return value


class PipelineSpec(BaseModel):
    """The pipeline behaviour for one source-and-ontology pair."""

    model_config = STRICT_MODEL_CONFIG

    name: str
    source_ref: str
    ontology_ref: str
    extraction: ExtractionSpec
    mapping: MappingSpec
    destination: DestinationSpec

    @field_validator("name", "source_ref", "ontology_ref")
    @classmethod
    def _names_are_snake_case(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(f"pipeline reference '{value}' must be snake_case")
        return value

    @model_validator(mode="after")
    def _validate_extraction_mode_for_v01(self) -> Self:
        # v0.1 only supports direct structured mapping. Other modes parse but
        # are not yet runnable; we still allow them so that v0.2 manifests
        # remain forward-compatible.
        return self


class PipelineManifest(BaseModel):
    """Top-level model for ``pipeline.yaml``."""

    model_config = STRICT_MODEL_CONFIG

    version: ManifestVersion
    pipeline: PipelineSpec
