"""In-memory graph object models produced by the mapping engine.

These are the objects a graph sink writes. They are deliberately simple
property bags with explicit identity (label + key property + key value
for nodes; label-key pairs on both endpoints for relationships) so that
upserts can be expressed idempotently regardless of the destination.

Key values are always carried as strings. CSV sources produce strings
natively; JSON sources may produce ints or other primitives that we
stringify here so that the same logical entity has a stable identity
regardless of how the data arrived.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from graphflow_core.manifests.common import (
    is_pascal_case,
    is_screaming_snake_case,
    is_snake_case,
)


class RecordProvenance(BaseModel):
    """Where a graph object came from in the source data.

    Attached to nodes and relationships so that downstream errors,
    review tooling, or audit logs can point back to the originating
    row or array element.
    """

    model_config = ConfigDict(extra="forbid")

    source_name: str
    source_path: str
    location: str


class GraphNode(BaseModel):
    """A graph node ready for upsert into a destination database."""

    model_config = ConfigDict(extra="forbid")

    label: str
    key_property: str
    key_value: str
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: RecordProvenance | None = None

    @field_validator("label")
    @classmethod
    def _label_pascal(cls, value: str) -> str:
        if not is_pascal_case(value):
            raise ValueError(f"GraphNode.label '{value}' must be PascalCase")
        return value

    @field_validator("key_property")
    @classmethod
    def _key_property_snake(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(f"GraphNode.key_property '{value}' must be snake_case")
        return value

    @field_validator("key_value")
    @classmethod
    def _key_value_non_empty(cls, value: str) -> str:
        if value == "":
            raise ValueError("GraphNode.key_value must be a non-empty string")
        return value

    def identity(self) -> tuple[str, str, str]:
        """Stable identity tuple used for duplicate detection and dedup."""
        return (self.label, self.key_property, self.key_value)


class GraphRelationship(BaseModel):
    """A graph relationship ready for upsert into a destination database.

    Endpoints are referenced by their node identity (label + key
    property + key value) rather than by object reference. This keeps
    relationships serialisable and lets the mapper emit them without
    needing every node already in memory.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    from_label: str
    from_key_property: str
    from_key_value: str
    to_label: str
    to_key_property: str
    to_key_value: str
    properties: dict[str, Any] = Field(default_factory=dict)
    provenance: RecordProvenance | None = None

    @field_validator("type")
    @classmethod
    def _type_screaming(cls, value: str) -> str:
        if not is_screaming_snake_case(value):
            raise ValueError(f"GraphRelationship.type '{value}' must be SCREAMING_SNAKE_CASE")
        return value

    @field_validator("from_label", "to_label")
    @classmethod
    def _endpoint_label_pascal(cls, value: str) -> str:
        if not is_pascal_case(value):
            raise ValueError(f"GraphRelationship endpoint label '{value}' must be PascalCase")
        return value

    @field_validator("from_key_property", "to_key_property")
    @classmethod
    def _endpoint_key_property_snake(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(
                f"GraphRelationship endpoint key_property '{value}' must be snake_case"
            )
        return value

    @field_validator("from_key_value", "to_key_value")
    @classmethod
    def _endpoint_key_value_non_empty(cls, value: str) -> str:
        if value == "":
            raise ValueError("GraphRelationship endpoint key_value must be a non-empty string")
        return value

    def from_identity(self) -> tuple[str, str, str]:
        return (self.from_label, self.from_key_property, self.from_key_value)

    def to_identity(self) -> tuple[str, str, str]:
        return (self.to_label, self.to_key_property, self.to_key_value)
