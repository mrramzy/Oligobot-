# -*- coding: utf-8 -*-
"""
Tests for entity_extractor module.
"""
import sys
import os
import json
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from entity_extractor import EntityExtractor, ENTITY_CATEGORIES, RELATIONSHIP_TYPES


@pytest.fixture
def extractor(tmp_path):
    """Create a fresh EntityExtractor with temporary storage."""
    storage = tmp_path / "test_entity_index.json"
    return EntityExtractor(storage_path=str(storage))


@pytest.fixture
def sample_text():
    """Sample medical text for extraction testing."""
    return (
        "Iron deficiency anemia is diagnosed by measuring serum ferritin levels. "
        "The Wright stain is used to visualize red blood cells and neutrophils. "
        "Malaria is caused by Plasmodium falciparum and identified via Giemsa stain. "
        "Reference range for hemoglobin is 12-16 g/dL for females."
    )


class TestEntityCategories:
    """Test entity category definitions."""

    def test_all_categories_defined(self):
        assert len(ENTITY_CATEGORIES) == 8
        assert "DISEASE" in ENTITY_CATEGORIES
        assert "TEST" in ENTITY_CATEGORIES
        assert "CELL" in ENTITY_CATEGORIES
        assert "PARASITE" in ENTITY_CATEGORIES

    def test_all_relationship_types_defined(self):
        assert len(RELATIONSHIP_TYPES) >= 10
        assert "DIAGNOSES" in RELATIONSHIP_TYPES
        assert "MEASURES" in RELATIONSHIP_TYPES
        assert "CAUSED_BY" in RELATIONSHIP_TYPES


class TestEntityExtraction:
    """Test entity extraction from text."""

    def test_extract_disease_entities(self, extractor, sample_text):
        entities = extractor.extract_entities_from_text(sample_text, source="test")
        disease_entities = [e for e in entities if e["category"] == "DISEASE"]
        names = [e["name"].lower() for e in disease_entities]
        assert any("anemia" in n for n in names)

    def test_extract_test_entities(self, extractor, sample_text):
        entities = extractor.extract_entities_from_text(sample_text, source="test")
        test_entities = [e for e in entities if e["category"] == "TEST"]
        names = [e["name"].lower() for e in test_entities]
        assert any("ferritin" in n for n in names)

    def test_extract_cell_entities(self, extractor, sample_text):
        entities = extractor.extract_entities_from_text(sample_text, source="test")
        cell_entities = [e for e in entities if e["category"] == "CELL"]
        names = [e["name"].lower() for e in cell_entities]
        assert any("neutrophil" in n for n in names)

    def test_extract_parasite_entities(self, extractor, sample_text):
        entities = extractor.extract_entities_from_text(sample_text, source="test")
        parasite_entities = [e for e in entities if e["category"] == "PARASITE"]
        names = [e["name"].lower() for e in parasite_entities]
        assert any("plasmodium" in n for n in names)

    def test_entity_has_source(self, extractor, sample_text):
        entities = extractor.extract_entities_from_text(sample_text, source="textbook")
        for entity in entities:
            assert "textbook" in entity["sources"]

    def test_entity_has_context_snippets(self, extractor, sample_text):
        entities = extractor.extract_entities_from_text(sample_text, source="test")
        for entity in entities:
            assert len(entity["context_snippets"]) > 0
            assert len(entity["context_snippets"][0]) <= 200

    def test_empty_text_returns_empty(self, extractor):
        entities = extractor.extract_entities_from_text("", source="test")
        assert entities == []

    def test_no_matches_returns_empty(self, extractor):
        entities = extractor.extract_entities_from_text("random unrelated text", source="test")
        assert entities == []


class TestRelationshipExtraction:
    """Test relationship extraction from text."""

    def test_extract_diagnoses_relationship(self, extractor, sample_text):
        relationships = extractor.extract_relationships(sample_text, source="test")
        diag_rels = [r for r in relationships if r["type"] == "DIAGNOSES"]
        assert len(diag_rels) > 0

    def test_extract_caused_by_relationship(self, extractor, sample_text):
        relationships = extractor.extract_relationships(sample_text, source="test")
        caused_rels = [r for r in relationships if r["type"] == "CAUSED_BY"]
        assert len(caused_rels) > 0

    def test_relationship_has_source_target(self, extractor, sample_text):
        relationships = extractor.extract_relationships(sample_text, source="test")
        for rel in relationships:
            assert "source" in rel
            assert "target" in rel
            assert "type" in rel

    def test_empty_text_returns_no_relationships(self, extractor):
        relationships = extractor.extract_relationships("", source="test")
        assert relationships == []


class TestEntitySearch:
    """Test entity search functionality."""

    def test_search_exact_match(self, extractor, sample_text):
        extractor.extract_entities_from_text(sample_text, source="test")
        results = extractor.search_entities("anemia", top_k=5)
        assert len(results) > 0
        assert any("anemia" in r["name"].lower() for r in results)

    def test_search_partial_match(self, extractor, sample_text):
        extractor.extract_entities_from_text(sample_text, source="test")
        results = extractor.search_entities("ferritin test", top_k=5)
        assert len(results) > 0

    def test_search_no_match(self, extractor, sample_text):
        extractor.extract_entities_from_text(sample_text, source="test")
        results = extractor.search_entities("xyznonexistent", top_k=5)
        assert len(results) == 0

    def test_search_respects_top_k(self, extractor, sample_text):
        extractor.extract_entities_from_text(sample_text, source="test")
        results = extractor.search_entities("anemia", top_k=2)
        assert len(results) <= 2


class TestRelatedEntities:
    """Test relationship traversal."""

    def test_get_related_entities(self, extractor, sample_text):
        extractor.extract_entities_from_text(sample_text, source="test")
        extractor.extract_relationships(sample_text, source="test")
        # Find an entity that has relationships
        for entity_id in list(extractor.entities.keys())[:5]:
            name = extractor.entities[entity_id]["name"]
            related = extractor.get_related_entities(name)
            if related:
                assert len(related) > 0
                assert "source" in related[0]
                assert "type" in related[0]
                break

    def test_get_entity_context(self, extractor, sample_text):
        extractor.extract_entities_from_text(sample_text, source="test")
        extractor.extract_relationships(sample_text, source="test")
        for entity_id in list(extractor.entities.keys())[:5]:
            name = extractor.entities[entity_id]["name"]
            context = extractor.get_entity_context(name)
            if context:
                assert len(context) > 0
                break


class TestPersistence:
    """Test index save/load."""

    def test_save_and_load(self, extractor, sample_text):
        extractor.extract_entities_from_text(sample_text, source="test")
        extractor.extract_relationships(sample_text, source="test")
        extractor._save_index()

        # Load in a new extractor
        extractor2 = EntityExtractor(storage_path=extractor.storage_path)
        assert len(extractor2.entities) == len(extractor.entities)
        assert len(extractor2.relationships) == len(extractor.relationships)

    def test_load_nonexistent_file(self, tmp_path):
        extractor = EntityExtractor(storage_path=str(tmp_path / "nonexistent.json"))
        assert len(extractor.entities) == 0
        assert len(extractor.relationships) == 0


class TestBuildFromChunks:
    """Test building index from document chunks."""

    def test_build_from_chunks(self, extractor):
        chunks = [
            {"content": "Iron deficiency anemia is common. Serum ferritin is low.", "metadata": {"source": "test"}},
            {"content": "Malaria is caused by Plasmodium. Giemsa stain confirms.", "metadata": {"source": "test"}},
        ]
        extractor.build_index_from_chunks(chunks, source="test")
        assert len(extractor.entities) > 0
        assert len(extractor.relationships) > 0

    def test_build_empty_chunks(self, extractor):
        extractor.build_index_from_chunks([], source="test")
        assert len(extractor.entities) == 0
