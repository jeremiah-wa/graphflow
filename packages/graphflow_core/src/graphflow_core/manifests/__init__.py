"""GraphFlow declarative manifest models.

This subpackage owns the Pydantic v2 models and YAML loader for the
four GraphFlow manifest files: ``source.yaml``, ``ontology.yaml``,
``pipeline.yaml`` and ``connections.yaml``.

Public surface:

- :class:`SourceSpec`, :class:`SourceManifest`
- :class:`OntologySpec`, :class:`OntologyManifest`
- :class:`PipelineSpec`, :class:`PipelineManifest`
- :class:`ConnectionSpec`, :class:`ConnectionsManifest`
- :class:`ConnectorManifest`
- :func:`load_source`, :func:`load_ontology`, :func:`load_pipeline`,
  :func:`load_connections`, :func:`load_connector`
- :class:`ManifestError`, :class:`ManifestValidationError`
"""

from __future__ import annotations

from graphflow_core.manifests.connections import (
    ConnectionsManifest,
    ConnectionSpec,
)
from graphflow_core.manifests.errors import (
    ManifestError,
    ManifestValidationError,
)
from graphflow_core.manifests.loader import (
    ConnectorManifest,
    load_connections,
    load_connector,
    load_ontology,
    load_pipeline,
    load_source,
)
from graphflow_core.manifests.ontology import (
    NodeKey,
    NodeSpec,
    OntologyManifest,
    OntologySpec,
    PropertySpec,
    RelationshipKey,
    RelationshipSpec,
)
from graphflow_core.manifests.pipeline import (
    DestinationSpec,
    ExtractionSpec,
    MappingSpec,
    NodeKeyMapping,
    NodeMapping,
    PipelineManifest,
    PipelineSpec,
    RelationshipMapping,
)
from graphflow_core.manifests.source import SourceManifest, SourceSpec

__all__ = [
    "ConnectionSpec",
    "ConnectionsManifest",
    "ConnectorManifest",
    "DestinationSpec",
    "ExtractionSpec",
    "ManifestError",
    "ManifestValidationError",
    "MappingSpec",
    "NodeKey",
    "NodeKeyMapping",
    "NodeMapping",
    "NodeSpec",
    "OntologyManifest",
    "OntologySpec",
    "PipelineManifest",
    "PipelineSpec",
    "PropertySpec",
    "RelationshipKey",
    "RelationshipMapping",
    "RelationshipSpec",
    "SourceManifest",
    "SourceSpec",
    "load_connections",
    "load_connector",
    "load_ontology",
    "load_pipeline",
    "load_source",
]
