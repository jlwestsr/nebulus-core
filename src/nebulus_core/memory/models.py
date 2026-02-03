"""Data models for the hybrid long-term memory system.

Pydantic models for entities, relations, and memory items used in both
the knowledge graph and vector stores.
"""

import time
import uuid

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Represents a node in the knowledge graph."""

    id: str = Field(
        ..., description="Unique identifier for the entity (e.g., 'Production Server')"
    )
    type: str = Field(
        ..., description="Type of the entity (e.g., 'Server', 'Person')"
    )
    properties: dict[str, str] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Relation(BaseModel):
    """Represents an edge in the knowledge graph."""

    source: str = Field(..., description="ID of the source entity")
    target: str = Field(..., description="ID of the target entity")
    relation: str = Field(
        ..., description="Type of relationship (e.g., 'HAS_IP', 'OWNED_BY')"
    )
    weight: float = Field(1.0, description="Confidence or importance weight")


class MemoryItem(BaseModel):
    """Represents a raw memory log or fact."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str = Field(..., description="The raw text content")
    timestamp: float = Field(default_factory=time.time)
    metadata: dict[str, str] = Field(default_factory=dict)
    archived: bool = Field(
        False, description="Whether this item has been consolidated"
    )


class GraphStats(BaseModel):
    """Statistics about the current state of the knowledge graph."""

    node_count: int
    edge_count: int
    entity_types: list[str]
