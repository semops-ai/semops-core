"""
Graph-based classifier using Neo4j for structural analysis.

This classifier uses Neo4j Graph Data Science (GDS) to evaluate:
- Orphan detection: Concepts disconnected from the main graph
- Hierarchy validation: Check for cycles, proper tree structure
- Community detection: Identify clusters and outliers
- Centrality scoring: Importance based on graph position

Requires Neo4j with GDS plugin and synced concept graph.
"""

from typing import Any

from neo4j import GraphDatabase

from .base import BaseClassifier, ClassificationResult, Settings


class GraphSettings(Settings):
    """Extended settings for Neo4j connection."""

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = ""  # Empty for auth=none
    neo4j_password: str = ""


class GraphClassifier(BaseClassifier):
    """
    Graph-based classifier using Neo4j GDS.

    Evaluates structural properties of concepts in the knowledge graph:
    - Connectivity: Is this concept connected to the main graph?
    - Hierarchy: Does it participate in valid taxonomic relationships?
    - Centrality: How important is this concept in the graph?
    - Community: What cluster does it belong to?

    Scores:
        - connectivity: 0.0 (isolated) to 1.0 (well-connected)
        - hierarchy_valid: boolean - no cycles in broader/narrower
        - pagerank: Relative importance (normalized)
        - community_id: Cluster identifier
        - is_orphan: boolean
        - promotion_ready: boolean
    """

    # Thresholds
    MIN_CONNECTIONS = 1  # Minimum edges to not be orphan
    MIN_PAGERANK_PERCENTILE = 0.1  # Bottom 10% flagged as low importance

    @property
    def classifier_id(self) -> str:
        return "graph-structure-v1"

    @property
    def classifier_version(self) -> str:
        return "1.0.0"

    def __init__(self) -> None:
        super().__init__()
        self.graph_settings = GraphSettings()
        self._driver = None

    @property
    def driver(self):
        """Lazy Neo4j driver."""
        if self._driver is None:
            auth = None
            if self.graph_settings.neo4j_user and self.graph_settings.neo4j_password:
                auth = (
                    self.graph_settings.neo4j_user,
                    self.graph_settings.neo4j_password,
                )
            self._driver = GraphDatabase.driver(
                self.graph_settings.neo4j_uri,
                auth=auth,
            )
        return self._driver

    def close(self) -> None:
        """Close connections."""
        super().close()
        if self._driver:
            self._driver.close()

    def _ensure_gds_projection(self) -> bool:
        """Ensure GDS graph projection exists."""
        with self.driver.session() as session:
            # Check if projection exists
            result = session.run("CALL gds.graph.exists('concept-graph')")
            record = result.single()
            if record and record["exists"]:
                return True

            # Create projection
            try:
                session.run("""
                    CALL gds.graph.project(
                        'concept-graph',
                        'Concept',
                        {
                            BROADER: {orientation: 'NATURAL'},
                            NARROWER: {orientation: 'NATURAL'},
                            RELATED: {orientation: 'UNDIRECTED'}
                        }
                    )
                """)
                return True
            except Exception as e:
                print(f"Error creating GDS projection: {e}")
                return False

    def _get_concept_stats(self, concept_id: str) -> dict[str, Any]:
        """Get graph statistics for a concept."""
        with self.driver.session() as session:
            # Get basic connectivity
            result = session.run(
                """
                MATCH (c:Concept {id: $id})
                OPTIONAL MATCH (c)-[r]-()
                RETURN
                    c.id as id,
                    c.approval_status as approval_status,
                    count(r) as degree,
                    c.pagerank as pagerank,
                    c.community as community
                """,
                id=concept_id,
            )
            record = result.single()

            if not record:
                return {"exists": False}

            return {
                "exists": True,
                "degree": record["degree"] or 0,
                "pagerank": record["pagerank"],
                "community": record["community"],
                "approval_status": record["approval_status"],
            }

    def _check_hierarchy_cycles(self, concept_id: str) -> bool:
        """Check if concept is part of a cycle in broader/narrower hierarchy."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = (c:Concept {id: $id})-[:BROADER*1..10]->(c)
                RETURN count(path) > 0 as has_cycle
                """,
                id=concept_id,
            )
            record = result.single()
            return record["has_cycle"] if record else False

    def _get_nearest_approved(self, concept_id: str) -> tuple[str | None, int | None]:
        """Find nearest approved concept and path length."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (start:Concept {id: $id})
                MATCH path = shortestPath((start)-[*1..5]-(approved:Concept))
                WHERE approved.approval_status = 'approved'
                  AND approved.id <> $id
                RETURN approved.id as nearest_id, length(path) as distance
                ORDER BY length(path)
                LIMIT 1
                """,
                id=concept_id,
            )
            record = result.single()
            if record:
                return record["nearest_id"], record["distance"]
            return None, None

    def _compute_pagerank(self) -> None:
        """Run PageRank on the graph and write back to nodes."""
        if not self._ensure_gds_projection():
            return

        with self.driver.session() as session:
            try:
                session.run("""
                    CALL gds.pageRank.write(
                        'concept-graph',
                        {writeProperty: 'pagerank'}
                    )
                """)
            except Exception as e:
                print(f"Error computing PageRank: {e}")

    def _detect_communities(self) -> None:
        """Run community detection and write back to nodes."""
        if not self._ensure_gds_projection():
            return

        with self.driver.session() as session:
            try:
                session.run("""
                    CALL gds.louvain.write(
                        'concept-graph',
                        {writeProperty: 'community'}
                    )
                """)
            except Exception as e:
                print(f"Error detecting communities: {e}")

    def _get_pagerank_percentile(self, pagerank: float | None) -> float:
        """Get percentile rank for a pagerank score."""
        if pagerank is None:
            return 0.0

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (c:Concept)
                WHERE c.pagerank IS NOT NULL
                WITH c.pagerank as pr
                ORDER BY pr
                WITH collect(pr) as scores
                RETURN
                    size([s IN scores WHERE s <= $pagerank]) * 1.0 / size(scores) as percentile
                """,
                pagerank=pagerank,
            )
            record = result.single()
            return record["percentile"] if record else 0.0

    def classify(
        self, target_type: str, target_id: str, content: dict[str, Any]
    ) -> ClassificationResult:
        """Run graph-based classification."""
        if target_type != "concept":
            return ClassificationResult(
                target_type=target_type,
                target_id=target_id,
                classifier_id=self.classifier_id,
                classifier_version=self.classifier_version,
                scores={"skipped": True},
                labels={"reason": "Graph classification only supports concepts"},
                confidence=None,
                rationale="Entity graph classification not implemented",
            )

        return self._classify_concept(target_id, content)

    def _classify_concept(
        self, concept_id: str, content: dict[str, Any]
    ) -> ClassificationResult:
        """Classify concept using graph structure."""

        # Get basic stats
        stats = self._get_concept_stats(concept_id)

        if not stats.get("exists"):
            return ClassificationResult(
                target_type="concept",
                target_id=concept_id,
                classifier_id=self.classifier_id,
                classifier_version=self.classifier_version,
                scores={"error": True, "in_neo4j": False},
                labels={"reason": "Concept not found in Neo4j - run sync first"},
                confidence=None,
                rationale="Concept must be synced to Neo4j before graph classification",
            )

        # Check for hierarchy cycles
        has_cycle = self._check_hierarchy_cycles(concept_id)

        # Find nearest approved concept
        nearest_approved_id, distance_to_approved = self._get_nearest_approved(
            concept_id
        )

        # Compute derived metrics
        degree = stats["degree"]
        is_orphan = degree < self.MIN_CONNECTIONS

        # Normalize connectivity (cap at 10 connections)
        connectivity = min(degree / 10.0, 1.0)

        # Get pagerank percentile
        pagerank = stats.get("pagerank")
        pagerank_percentile = self._get_pagerank_percentile(pagerank)

        # Determine promotion readiness
        promotion_ready = (
            not is_orphan
            and not has_cycle
            and pagerank_percentile >= self.MIN_PAGERANK_PERCENTILE
        )

        scores = {
            "degree": degree,
            "connectivity": round(connectivity, 3),
            "pagerank": round(pagerank, 6) if pagerank else None,
            "pagerank_percentile": round(pagerank_percentile, 3),
            "is_orphan": is_orphan,
            "has_hierarchy_cycle": has_cycle,
            "distance_to_approved": distance_to_approved,
            "promotion_ready": promotion_ready,
        }

        labels: dict[str, Any] = {
            "community": stats.get("community"),
        }
        if nearest_approved_id:
            labels["nearest_approved"] = nearest_approved_id
        if is_orphan:
            labels["issue"] = "orphan"
        elif has_cycle:
            labels["issue"] = "hierarchy_cycle"

        # Build rationale
        rationale_parts = []
        rationale_parts.append(f"Degree: {degree} connections")

        if is_orphan:
            rationale_parts.append("ORPHAN: No connections to other concepts")
        if has_cycle:
            rationale_parts.append("CYCLE: Part of broader/narrower cycle")
        if pagerank is not None:
            rationale_parts.append(
                f"PageRank: {pagerank_percentile:.0%} percentile"
            )
        if nearest_approved_id:
            rationale_parts.append(
                f"Nearest approved: {nearest_approved_id} ({distance_to_approved} hops)"
            )

        input_text = f"{concept_id}|{stats.get('approval_status', '')}"

        return ClassificationResult(
            target_type="concept",
            target_id=concept_id,
            classifier_id=self.classifier_id,
            classifier_version=self.classifier_version,
            scores=scores,
            labels=labels,
            confidence=0.95,  # Graph metrics are deterministic
            rationale="; ".join(rationale_parts),
            input_hash=self.compute_input_hash(input_text),
        )

    def run_graph_algorithms(self) -> None:
        """Run PageRank and community detection on the full graph."""
        print("Computing PageRank...")
        self._compute_pagerank()
        print("Detecting communities...")
        self._detect_communities()
        print("Graph algorithms complete.")

    def classify_all_concepts(self) -> list[str]:
        """
        Classify all concepts in Neo4j.

        Should be run after sync_neo4j.py and run_graph_algorithms().
        """
        classification_ids = []

        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Concept)
                WHERE c.approval_status = 'pending'
                RETURN c.id as id, c.preferred_label as label,
                       c.definition as definition, c.provenance as provenance
            """)

            for record in result:
                content = {
                    "preferred_label": record["label"],
                    "definition": record["definition"],
                    "provenance": record["provenance"],
                }
                try:
                    cid = self.classify_and_save("concept", record["id"], content)
                    classification_ids.append(cid)
                    print(f"Classified concept: {record['id']}")
                except Exception as e:
                    print(f"Error classifying {record['id']}: {e}")

        return classification_ids
