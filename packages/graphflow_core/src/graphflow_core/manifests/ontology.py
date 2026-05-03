"""``ontology.yaml`` manifest models.

The ontology manifest describes the valid graph model: node labels,
relationship types, and their properties. Mapping logic does not live
here; this manifest only declares *what is allowed* in the graph.
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

PropertyType = Literal["string", "integer", "float", "boolean", "date", "datetime"]
GraphModel = Literal["property_graph"]
RelationshipKeyStrategy = Literal["endpoints_and_type", "explicit_property"]


class PropertySpec(BaseModel):
    """A node or relationship property declaration."""

    model_config = STRICT_MODEL_CONFIG

    type: PropertyType
    required: bool = False


class NodeKey(BaseModel):
    """Identifies which property uniquely keys a node."""

    model_config = STRICT_MODEL_CONFIG

    property: str

    @field_validator("property")
    @classmethod
    def _property_is_snake_case(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(f"node key.property '{value}' must be snake_case")
        return value


class RelationshipKey(BaseModel):
    """Identifies how a relationship instance is keyed for idempotent upsert."""

    model_config = STRICT_MODEL_CONFIG

    strategy: RelationshipKeyStrategy
    property: str | None = None

    @model_validator(mode="after")
    def _explicit_strategy_requires_property(self) -> Self:
        if self.strategy == "explicit_property" and not self.property:
            raise ValueError(
                "relationship key with strategy 'explicit_property' must set 'property'"
            )
        if self.strategy == "endpoints_and_type" and self.property is not None:
            raise ValueError(
                "relationship key with strategy 'endpoints_and_type' must not set 'property'"
            )
        return self


class NodeSpec(BaseModel):
    """A node label declaration in the ontology."""

    model_config = STRICT_MODEL_CONFIG

    label: str
    key: NodeKey
    properties: dict[str, PropertySpec] = Field(default_factory=dict)

    @field_validator("label")
    @classmethod
    def _label_is_pascal_case(cls, value: str) -> str:
        if not is_pascal_case(value):
            raise ValueError(f"node label '{value}' must be PascalCase (e.g. 'Company')")
        return value

    @field_validator("properties")
    @classmethod
    def _property_names_are_snake_case(
        cls, value: dict[str, PropertySpec]
    ) -> dict[str, PropertySpec]:
        for name in value:
            if not is_snake_case(name):
                raise ValueError(f"property name '{name}' must be snake_case")
        return value

    @model_validator(mode="after")
    def _key_property_must_exist(self) -> Self:
        if self.key.property not in self.properties:
            raise ValueError(
                f"node '{self.label}' key.property '{self.key.property}' is not "
                f"declared in properties. Known properties: "
                f"{sorted(self.properties)}"
            )
        return self


class RelationshipSpec(BaseModel):
    """A relationship type declaration in the ontology."""

    model_config = STRICT_MODEL_CONFIG

    type: str
    from_label: str = Field(alias="from")
    to: str
    key: RelationshipKey
    properties: dict[str, PropertySpec] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _type_is_screaming_snake(cls, value: str) -> str:
        if not is_screaming_snake_case(value):
            raise ValueError(
                f"relationship type '{value}' must be SCREAMING_SNAKE_CASE (e.g. 'OFFICER_OF')"
            )
        return value

    @field_validator("from_label", "to")
    @classmethod
    def _endpoint_label_is_pascal(cls, value: str) -> str:
        if not is_pascal_case(value):
            raise ValueError(f"relationship endpoint label '{value}' must be PascalCase")
        return value

    @field_validator("properties")
    @classmethod
    def _property_names_are_snake_case(
        cls, value: dict[str, PropertySpec]
    ) -> dict[str, PropertySpec]:
        for name in value:
            if not is_snake_case(name):
                raise ValueError(f"property name '{name}' must be snake_case")
        return value


class OntologySpec(BaseModel):
    """The graph model declared by an ontology manifest."""

    model_config = STRICT_MODEL_CONFIG

    name: str
    graph_model: GraphModel = "property_graph"
    nodes: list[NodeSpec]
    relationships: list[RelationshipSpec] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_is_snake_case(cls, value: str) -> str:
        if not is_snake_case(value):
            raise ValueError(f"ontology.name '{value}' must be snake_case")
        return value

    @model_validator(mode="after")
    def _check_internal_consistency(self) -> Self:
        labels = [node.label for node in self.nodes]
        duplicates = sorted({label for label in labels if labels.count(label) > 1})
        if duplicates:
            raise ValueError(f"ontology has duplicate node labels: {duplicates}")
        label_set = set(labels)
        for rel in self.relationships:
            if rel.from_label not in label_set:
                raise ValueError(
                    f"relationship '{rel.type}' references unknown 'from' label "
                    f"'{rel.from_label}'. Known labels: {sorted(label_set)}"
                )
            if rel.to not in label_set:
                raise ValueError(
                    f"relationship '{rel.type}' references unknown 'to' label "
                    f"'{rel.to}'. Known labels: {sorted(label_set)}"
                )
        return self

    def node_labels(self) -> set[str]:
        """Convenience accessor: set of declared node labels."""
        return {node.label for node in self.nodes}

    def relationship_types(self) -> set[str]:
        """Convenience accessor: set of declared relationship type names."""
        return {rel.type for rel in self.relationships}


class OntologyManifest(BaseModel):
    """Top-level model for ``ontology.yaml``."""

    model_config = STRICT_MODEL_CONFIG

    version: ManifestVersion
    ontology: OntologySpec
