"""GraphFlow source readers.

This subpackage owns parsers and readers that turn declarative
:class:`graphflow_core.manifests.SourceSpec` definitions into iterables
of :class:`ParsedRecord` objects. Concrete readers (CSV, JSON, ...) live
alongside :class:`SourceReader`, the structural protocol every reader
must satisfy.
"""

from __future__ import annotations

from graphflow_core.sources.base import ParsedRecord, SourceReader

__all__ = [
    "ParsedRecord",
    "SourceReader",
]
