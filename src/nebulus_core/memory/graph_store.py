"""Knowledge graph store backed by NetworkX.

Persists a directed graph to a JSON file. Used for long-term
structured knowledge extracted from episodic memories.
"""

import json
import logging
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

from nebulus_core.memory.models import Entity, GraphStats, Relation

logger = logging.getLogger(__name__)


class GraphStore:
    """Directed knowledge graph with JSON file persistence.

    Args:
        storage_path: Path to the JSON file for graph persistence.
    """

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.graph = nx.DiGraph()
        self._ensure_storage_dir()
        self._load()

    def _ensure_storage_dir(self) -> None:
        """Create parent directories if they don't exist."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        """Load graph from JSON file if it exists."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = json.load(f)
                self.graph = json_graph.node_link_graph(
                    data, directed=True, edges="links"
                )
                logger.info(
                    "Loaded graph from %s with %d nodes.",
                    self.storage_path,
                    self.graph.number_of_nodes(),
                )
            except Exception as e:
                logger.error("Failed to load graph: %s", e)
                self.graph = nx.DiGraph()
        else:
            logger.info("No existing graph found. Initialized empty graph.")

    def _save(self) -> None:
        """Persist graph to JSON file."""
        try:
            data = json_graph.node_link_data(self.graph, edges="links")
            with open(self.storage_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error("Failed to save graph: %s", e)

    def add_entity(self, entity: Entity) -> None:
        """Add a node to the graph. Idempotent.

        Args:
            entity: The entity to add.
        """
        self.graph.add_node(entity.id, type=entity.type, **entity.properties)
        self._save()

    def add_relation(self, relation: Relation) -> None:
        """Add a directional edge between nodes.

        Auto-creates missing source/target nodes as type 'Unknown'.

        Args:
            relation: The relation to add.
        """
        if not self.graph.has_node(relation.source):
            logger.warning(
                "Source node %s does not exist. Adding as generic entity.",
                relation.source,
            )
            self.graph.add_node(relation.source, type="Unknown")

        if not self.graph.has_node(relation.target):
            logger.warning(
                "Target node %s does not exist. Adding as generic entity.",
                relation.target,
            )
            self.graph.add_node(relation.target, type="Unknown")

        self.graph.add_edge(
            relation.source,
            relation.target,
            relation=relation.relation,
            weight=relation.weight,
        )
        self._save()

    def get_neighbors(self, node_id: str) -> list[tuple[str, str]]:
        """Get 1-hop neighbors for a node.

        Args:
            node_id: The node to query.

        Returns:
            List of (relation_type, target_node_id) tuples.
        """
        if not self.graph.has_node(node_id):
            return []

        results = []
        for neighbor in self.graph.neighbors(node_id):
            edge_data = self.graph.get_edge_data(node_id, neighbor)
            relation_type = edge_data.get("relation", "RELATED_TO")
            results.append((relation_type, neighbor))
        return results

    def get_stats(self) -> GraphStats:
        """Return current graph statistics.

        Returns:
            GraphStats with node count, edge count, and entity types.
        """
        types = set()
        for _, data in self.graph.nodes(data=True):
            if "type" in data:
                types.add(data["type"])

        return GraphStats(
            node_count=self.graph.number_of_nodes(),
            edge_count=self.graph.number_of_edges(),
            entity_types=sorted(types),
        )
