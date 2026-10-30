"""
AyurMitra — Traceable Knowledge Graph (NetworkX)
=================================================
A lightweight, inspectable knowledge graph connecting:
  - Doshas & Fundamental Concepts (from WHO & NAMASTE)
  - Medicinal Plants & Herbs (from IMPPAT 2.0 & API)
  - Catalogued Therapeutic Topics & Properties
  - Educational Symptoms & Concept Associations

Strict Provenance Rules:
  - Every edge stores source_id, locator, and review_status.
  - Traditional Ayurvedic concepts are strictly distinguished from biomedical diagnoses.
  - Edges are purely educational references, not claims of clinical effectiveness.
"""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

from app.config import KG_PKL, DATA_PROC, LICENCE_NOTES


class AyurKnowledgeGraph:
    """NetworkX-based knowledge graph with edge provenance."""

    def __init__(self, graph_path: Path = KG_PKL):
        self.graph_path = graph_path
        self.graph = nx.DiGraph()
        self._load_or_build()

    def _load_or_build(self) -> None:
        if self.graph_path.exists():
            try:
                with open(self.graph_path, "rb") as f:
                    self.graph = pickle.load(f)
                return
            except Exception:
                pass
        self._build_graph()

    def _build_graph(self) -> None:
        self.graph = nx.DiGraph()

        # 1. Fundamental Doshas & Principles (from NAMASTE & WHO)
        doshas = [
            ("Vata", "Governs bodily movement, nerve impulses, respiration, and elimination. Composed of Air and Space."),
            ("Pitta", "Governs digestion, metabolism, body temperature, and transformation. Composed of Fire and Water."),
            ("Kapha", "Governs biological structure, cohesion, lubrication, and stability. Composed of Earth and Water."),
        ]
        for d_name, d_desc in doshas:
            self.graph.add_node(
                d_name,
                node_type="Dosha",
                description=d_desc,
                source_id="NAMASTE_ayu-sat-table-a",
                locator="Code SAT-A",
                review_status="verified"
            )

        # Tridosha collective node
        self.graph.add_node(
            "Tridosha",
            node_type="Principle",
            description="The triad of functional biological humors in Ayurvedic physiology.",
            source_id="WHO_9789240064935",
            locator="page 15",
            review_status="verified"
        )
        for d_name, _ in doshas:
            self.graph.add_edge(
                "Tridosha", d_name,
                relation="comprises",
                source_id="WHO_9789240064935",
                locator="page 15",
                review_status="verified"
            )

        # Core Concepts
        concepts = [
            ("Agni", "Principle", "Digestive and metabolic fire essential for health.", "SAT-A.2"),
            ("Ama", "Concept", "Undigested toxic metabolic byproduct resulting from weak Agni.", "SAT-A.3"),
            ("Ojas", "Concept", "Subtle essence supporting immunity and vitality.", "SAT-A.4"),
            ("Prakriti", "Principle", "Individual baseline physiological constitution.", "SAT-A.5"),
            ("Rasayana", "Discipline", "Ayurvedic science of rejuvenation and longevity.", "SAT-A.6"),
            ("Panchakarma", "Therapy", "Five classical bio-cleansing procedures.", "SAT-A.7"),
        ]
        for c_name, c_type, c_desc, c_code in concepts:
            self.graph.add_node(
                c_name,
                node_type=c_type,
                description=c_desc,
                source_id="NAMASTE_ayu-sat-table-a",
                locator=f"Code {c_code}",
                review_status="verified"
            )

        self.graph.add_edge(
            "Agni", "Ama",
            relation="impaired_leads_to",
            source_id="NAMASTE_ayu-sat-table-a",
            locator="Code SAT-A.3",
            review_status="verified"
        )
        self.graph.add_edge(
            "Agni", "Ojas",
            relation="optimal_nourishes",
            source_id="NAMASTE_ayu-sat-table-a",
            locator="Code SAT-A.4",
            review_status="verified"
        )

        # 2. Medicinal Plants & Formulations (IMPPAT 2.0 & API)
        herbs = [
            ("Ashwagandha", "Withania somnifera", "Solanaceae", "Rasayana, stress adaptation, fatigue"),
            ("Triphala", "Terminalia chebula, T. bellirica, Phyllanthus emblica", "Multi-ingredient", "Digestive balance, eye health, mild laxative"),
            ("Tulsi", "Ocimum tenuiflorum", "Lamiaceae", "Respiratory comfort, anti-cough, immune support"),
            ("Neem", "Azadirachta indica", "Meliaceae", "Skin purification, bitter tonic, Pitta-Kapha balance"),
            ("Brahmi", "Bacopa monnieri", "Plantaginaceae", "Cognitive clarity, memory, nervous system support"),
            ("Shatavari", "Asparagus racemosus", "Asparagaceae", "Nourishing tonic, reproductive vitality, Pitta pacifier"),
            ("Guggulu", "Commiphora mukul", "Burseraceae", "Joint support, lipid metabolism, Vata-Kapha balance"),
            ("Amalaki", "Phyllanthus emblica", "Phyllanthaceae", "Natural antioxidant, Pitta pacifying, digestive support"),
        ]
        for h_name, h_bot, h_fam, h_uses in herbs:
            self.graph.add_node(
                h_name,
                node_type="Herb",
                botanical_name=h_bot,
                family=h_fam,
                recorded_uses=h_uses,
                source_id="IMPPAT_2.0",
                locator="Plant Registry",
                review_status="verified"
            )
            # Edge from herb to primary associated concept
            if "Rasayana" in h_uses:
                self.graph.add_edge(
                    h_name, "Rasayana",
                    relation="classified_under",
                    source_id="IMPPAT_2.0",
                    locator="TherapeuticUse_Plant_Association",
                    review_status="verified"
                )

        # 3. Educational Symptom Mappings (strictly non-diagnostic)
        symptom_mappings = [
            ("Dry Skin", "Vata", "Dryness and roughness are traditional indicators of aggravated Vata.", "WHO_9789240064935", "page 45"),
            ("Joint Stiffness", "Vata", "Joint crepitation and dryness are linked to Vata in classical texts.", "WHO_9789240064935", "page 46"),
            ("Burning Sensation", "Pitta", "Heat and burning sensation correspond to elevated Pitta humor.", "WHO_9789240064935", "page 50"),
            ("Acid Reflux", "Pitta", "Sour regurgitation is traditionally associated with Amla-Pitta.", "WHO_9789240064935", "page 52"),
            ("Sluggish Digestion", "Kapha", "Heaviness and slow digestion relate to high Kapha / low Agni.", "NAMASTE_ayu-sat-table-a", "Code SAT-A.2"),
            ("Excessive Mucus", "Kapha", "Congestion and mucosal accumulation reflect increased Kapha.", "WHO_9789240064935", "page 58"),
        ]
        for s_phrase, d_target, note, src_id, loc in symptom_mappings:
            self.graph.add_node(
                s_phrase,
                node_type="SymptomPhrase",
                description=note,
                source_id=src_id,
                locator=loc,
                review_status="verified"
            )
            self.graph.add_edge(
                s_phrase, d_target,
                relation="may_be_associated_with_dosha",
                note=note,
                source_id=src_id,
                locator=loc,
                review_status="verified"
            )

        # Cache graph
        DATA_PROC.mkdir(parents=True, exist_ok=True)
        with open(self.graph_path, "wb") as f:
            pickle.dump(self.graph, f)

    def query_concept(self, concept_name: str) -> Dict[str, Any]:
        """Lookup node details and connected neighbors with provenance."""
        # Case-insensitive search
        matched_node = None
        for node in self.graph.nodes:
            if node.lower() == concept_name.lower():
                matched_node = node
                break

        if not matched_node:
            return {"found": False, "concept": concept_name, "attributes": {}, "connections": [], "neighbors": []}  # F10: same keys as found-case

        attrs = self.graph.nodes[matched_node]
        neighbors = []
        for nbr in self.graph.neighbors(matched_node):
            edge_data = self.graph.get_edge_data(matched_node, nbr)
            nbr_attrs = self.graph.nodes[nbr]
            neighbors.append({
                "target": nbr,
                "target_type": nbr_attrs.get("node_type", "Unknown"),
                "relation": edge_data.get("relation", "related_to"),
                "source_id": edge_data.get("source_id", "Unknown"),
                "locator": edge_data.get("locator", "Unknown"),
            })

        # Also get in-edges
        for pred in self.graph.predecessors(matched_node):
            edge_data = self.graph.get_edge_data(pred, matched_node)
            pred_attrs = self.graph.nodes[pred]
            neighbors.append({
                "source": pred,
                "source_type": pred_attrs.get("node_type", "Unknown"),
                "relation": edge_data.get("relation", "related_to"),
                "source_id": edge_data.get("source_id", "Unknown"),
                "locator": edge_data.get("locator", "Unknown"),
            })

        return {
            "found": True,
            "concept": matched_node,
            "attributes": attrs,
            "connections": neighbors,
            "neighbors": neighbors,  # F10: alias kept for callers of the not-found shape
        }

