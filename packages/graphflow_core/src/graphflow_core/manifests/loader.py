"""YAML loaders and cross-manifest validation for connector folders.

A *connector folder* is a directory containing the four manifest files:

```text
source.yaml
ontology.yaml
pipeline.yaml
connections.yaml
```

The loader functions parse and validate each file individually. The
:func:`load_connector` helper additionally cross-validates references
between manifests (for example, that ``pipeline.source_ref`` matches
``source.name``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from graphflow_core.manifests.connections import ConnectionsManifest
from graphflow_core.manifests.errors import (
    ManifestError,
    ManifestValidationError,
)
from graphflow_core.manifests.ontology import OntologyManifest
from graphflow_core.manifests.pipeline import PipelineManifest
from graphflow_core.manifests.source import SourceManifest

SOURCE_FILENAME = "source.yaml"
ONTOLOGY_FILENAME = "ontology.yaml"
PIPELINE_FILENAME = "pipeline.yaml"
CONNECTIONS_FILENAME = "connections.yaml"


class ConnectorManifest(BaseModel):
    """Validated bundle of the four manifests in a connector folder."""

    source: SourceManifest
    ontology: OntologyManifest
    pipeline: PipelineManifest
    connections: ConnectionsManifest


def _read_yaml(path: Path) -> Any:
    if not path.exists():
        raise ManifestError(f"Manifest file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem failure
        raise ManifestError(f"Could not read {path}: {exc}") from exc
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ManifestError(f"Invalid YAML in {path}: {exc}") from exc


def _format_validation_error(path: Path, exc: ValidationError) -> ManifestValidationError:
    issues: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"]) or "<root>"
        issues.append(f"{loc}: {err['msg']}")
    return ManifestValidationError(issues, path=path)


M = TypeVar("M", bound=BaseModel)


def _load_model(path: Path, model: type[M]) -> M:
    raw = _read_yaml(path)
    if raw is None:
        raise ManifestValidationError([f"{path.name} is empty"], path=path)
    if not isinstance(raw, dict):
        raise ManifestValidationError(
            [f"{path.name} top-level must be a mapping, got {type(raw).__name__}"],
            path=path,
        )
    try:
        return model.model_validate(raw)
    except ValidationError as exc:
        raise _format_validation_error(path, exc) from exc


def load_source(path: Path) -> SourceManifest:
    """Load and validate a ``source.yaml`` file."""
    return _load_model(path, SourceManifest)


def load_ontology(path: Path) -> OntologyManifest:
    """Load and validate an ``ontology.yaml`` file."""
    return _load_model(path, OntologyManifest)


def load_pipeline(path: Path) -> PipelineManifest:
    """Load and validate a ``pipeline.yaml`` file."""
    return _load_model(path, PipelineManifest)


def load_connections(path: Path) -> ConnectionsManifest:
    """Load and validate a ``connections.yaml`` file."""
    return _load_model(path, ConnectionsManifest)


def _cross_validate(
    folder: Path,
    source: SourceManifest,
    ontology: OntologyManifest,
    pipeline: PipelineManifest,
    connections: ConnectionsManifest,
) -> list[str]:
    """Return a list of cross-manifest issues. Empty list means valid."""
    issues: list[str] = []
    pipe = pipeline.pipeline
    src = source.source
    onto = ontology.ontology

    if pipe.source_ref != src.name:
        issues.append(
            f"pipeline.source_ref '{pipe.source_ref}' does not match "
            f"source.name '{src.name}' in {SOURCE_FILENAME}"
        )
    if pipe.ontology_ref != onto.name:
        issues.append(
            f"pipeline.ontology_ref '{pipe.ontology_ref}' does not match "
            f"ontology.name '{onto.name}' in {ONTOLOGY_FILENAME}"
        )

    known_labels = onto.node_labels()
    known_rel_types = onto.relationship_types()

    for index, node in enumerate(pipe.mapping.nodes):
        loc = f"pipeline.mapping.nodes[{index}]"
        if node.label not in known_labels:
            issues.append(
                f"{loc}.label '{node.label}' is not declared in ontology. "
                f"Known labels: {sorted(known_labels)}"
            )
            continue
        ontology_node = next(n for n in onto.nodes if n.label == node.label)
        if ontology_node.key.property not in node.properties:
            issues.append(
                f"{loc} does not map the key property "
                f"'{ontology_node.key.property}' required by ontology node "
                f"'{node.label}'"
            )

    for index, rel in enumerate(pipe.mapping.relationships):
        loc = f"pipeline.mapping.relationships[{index}]"
        if rel.type not in known_rel_types:
            issues.append(
                f"{loc}.type '{rel.type}' is not declared in ontology. "
                f"Known types: {sorted(known_rel_types)}"
            )
            continue
        ontology_rel = next(r for r in onto.relationships if r.type == rel.type)
        if rel.from_node.label != ontology_rel.from_label:
            issues.append(
                f"{loc}.from.label '{rel.from_node.label}' does not match "
                f"ontology relationship '{rel.type}' from-label "
                f"'{ontology_rel.from_label}'"
            )
        if rel.to_node.label != ontology_rel.to:
            issues.append(
                f"{loc}.to.label '{rel.to_node.label}' does not match "
                f"ontology relationship '{rel.type}' to-label "
                f"'{ontology_rel.to}'"
            )

    if pipe.destination.connection_ref not in connections.connections:
        issues.append(
            f"pipeline.destination.connection_ref "
            f"'{pipe.destination.connection_ref}' is not declared in "
            f"{CONNECTIONS_FILENAME}. Known connections: "
            f"{sorted(connections.connections)}"
        )
    else:
        connection = connections.connections[pipe.destination.connection_ref]
        if pipe.destination.type != connection.type:
            issues.append(
                f"pipeline.destination.type '{pipe.destination.type}' does not "
                f"match connection '{pipe.destination.connection_ref}' type "
                f"'{connection.type}'"
            )

    # Source path is interpreted relative to the connector folder. We do
    # not require the file to exist here (validation should not depend on
    # local data fixtures), but the path must not be absolute or escape the
    # folder.
    source_path = Path(src.path)
    if source_path.is_absolute():
        issues.append(f"source.path '{src.path}' must be relative to the connector folder")
    else:
        resolved = (folder / source_path).resolve()
        try:
            resolved.relative_to(folder.resolve())
        except ValueError:
            issues.append(f"source.path '{src.path}' must not escape the connector folder")

    return issues


def load_connector(folder: Path) -> ConnectorManifest:
    """Load, validate, and cross-validate all four manifests in ``folder``.

    Raises :class:`ManifestValidationError` if any manifest is invalid or
    if cross-manifest references are inconsistent.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise ManifestError(f"Connector folder not found: {folder}")

    parse_issues: list[str] = []
    source: SourceManifest | None = None
    ontology: OntologyManifest | None = None
    pipeline: PipelineManifest | None = None
    connections: ConnectionsManifest | None = None

    targets: list[tuple[str, Any]] = [
        (SOURCE_FILENAME, load_source),
        (ONTOLOGY_FILENAME, load_ontology),
        (PIPELINE_FILENAME, load_pipeline),
        (CONNECTIONS_FILENAME, load_connections),
    ]
    results: dict[str, Any] = {}
    for name, fn in targets:
        try:
            results[name] = fn(folder / name)
        except ManifestValidationError as exc:
            parse_issues.extend(f"{name}: {issue}" for issue in exc.issues)
        except ManifestError as exc:
            parse_issues.append(f"{name}: {exc}")

    if parse_issues:
        raise ManifestValidationError(parse_issues, path=folder)

    source = results[SOURCE_FILENAME]
    ontology = results[ONTOLOGY_FILENAME]
    pipeline = results[PIPELINE_FILENAME]
    connections = results[CONNECTIONS_FILENAME]
    assert source is not None
    assert ontology is not None
    assert pipeline is not None
    assert connections is not None

    cross_issues = _cross_validate(folder, source, ontology, pipeline, connections)
    if cross_issues:
        raise ManifestValidationError(cross_issues, path=folder)

    return ConnectorManifest(
        source=source,
        ontology=ontology,
        pipeline=pipeline,
        connections=connections,
    )
