"""Memory consolidator ("sleep cycle").

Fetches unarchived episodic memories, uses the LLM to extract structured
facts (entities and relations), and updates the knowledge graph.
"""

import json
import logging

from nebulus_core.llm.client import LLMClient
from nebulus_core.memory.graph_store import GraphStore
from nebulus_core.memory.models import Entity, Relation
from nebulus_core.vector.episodic import EpisodicMemory

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
Analyze the following text and extract key entities and relationships.
Return ONLY a JSON object with this structure:
{{
    "entities": [{{"id": "EntityName", "type": "EntityType"}}],
    "relations": [
        {{"source": "EntityName", "target": "TargetEntity",
          "relation": "RELATION_TYPE"}}
    ]
}}

Text: "{text}"
"""


class Consolidator:
    """Extracts structured knowledge from episodic memories.

    Args:
        episodic: EpisodicMemory instance for fetching raw memories.
        graph: GraphStore instance for persisting extracted knowledge.
        llm: LLMClient instance for LLM inference.
        model: Model name to use for extraction.
    """

    def __init__(
        self,
        episodic: EpisodicMemory,
        graph: GraphStore,
        llm: LLMClient,
        model: str,
    ) -> None:
        self.episodic = episodic
        self.graph = graph
        self.llm = llm
        self.model = model

    def consolidate(self) -> str:
        """Run the consolidation cycle.

        Returns:
            Summary string describing what was processed.
        """
        logger.info("Starting memory consolidation cycle...")

        memories = self.episodic.get_unarchived(n_results=20)
        if not memories:
            logger.info("No new memories to consolidate.")
            return "No new memories to consolidate."

        logger.info("Processing %d memory items.", len(memories))

        processed_ids: list[str] = []
        total_entities = 0
        total_relations = 0

        for memory in memories:
            try:
                facts = self._extract_facts(memory.content)
                counts = self._update_graph(facts)
                total_entities += counts[0]
                total_relations += counts[1]
                processed_ids.append(memory.id)
            except Exception as e:
                logger.error("Failed to process memory %s: %s", memory.id, e)

        if processed_ids:
            self.episodic.mark_archived(processed_ids)
            logger.info("Archived %d memory items.", len(processed_ids))

        return (
            f"Processed {len(processed_ids)} memories, "
            f"extracted {total_entities} entities and "
            f"{total_relations} relations."
        )

    def _extract_facts(self, text: str) -> dict:
        """Use the LLM to extract entities and relations from text.

        Args:
            text: Raw memory text.

        Returns:
            Dict with 'entities' and 'relations' lists.
        """
        prompt = _EXTRACTION_PROMPT.format(text=text)

        try:
            content = self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
            )

            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(content[start:end])
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON in LLM response.")
                    return {"entities": [], "relations": []}
            else:
                logger.warning("Could not find JSON in LLM response.")
                return {"entities": [], "relations": []}
        except Exception as e:
            logger.error("LLM extraction failed: %s", e)
            return {"entities": [], "relations": []}

    def _update_graph(self, facts: dict) -> tuple[int, int]:
        """Update the graph store with extracted facts.

        Args:
            facts: Dict with 'entities' and 'relations' lists.

        Returns:
            Tuple of (entities_added, relations_added).
        """
        entity_count = 0
        relation_count = 0

        for ent in facts.get("entities", []):
            try:
                entity = Entity(
                    id=ent["id"],
                    type=ent.get("type", "Unknown"),
                    properties={},
                )
                self.graph.add_entity(entity)
                entity_count += 1
            except Exception as e:
                logger.warning("Skipping invalid entity %s: %s", ent, e)

        for rel in facts.get("relations", []):
            try:
                relation = Relation(
                    source=rel["source"],
                    target=rel["target"],
                    relation=rel["relation"],
                    weight=1.0,
                )
                self.graph.add_relation(relation)
                relation_count += 1
            except Exception as e:
                logger.warning("Skipping invalid relation %s: %s", rel, e)

        return entity_count, relation_count
