"""Mapping issues collected during a mapping run.

A :class:`MappingIssue` describes a single problem the mapper found
while turning records into graph objects. The mapper accumulates issues
rather than raising on the first one so that callers can present a
complete, actionable list to the user.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

MappingIssueSeverity = Literal["error", "warning"]


class MappingIssue(BaseModel):
    """A problem found while mapping a record to graph objects."""

    model_config = ConfigDict(extra="forbid")

    severity: MappingIssueSeverity
    message: str
    source_name: str
    location: str
    target: str
    """A short pointer at what was being mapped, e.g. 'Company.company_number'."""
