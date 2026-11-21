# -*- coding: utf-8 -*-
"""
Demo: Entity Extraction Pipeline
Shows how extracted entities enhance retrieval.
"""
import asyncio
import sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from entity_extractor import get_entity_extractor

async def demo():
    ext = get_entity_extractor()

    # Sample medical text (simulating a knowledge base chunk)
    sample_texts = [
        {
            "text": "Iron deficiency anemia is confirmed by low serum ferritin (<15 ng/mL), "
                    "low serum iron, and elevated TIBC. The CBC shows microcytic anemia with "
                    "MCV <80 fL, MCH <27 pg, and RDW >14.5%. A peripheral blood smear reveals "
                    "microcytic hypochromic red cells, target cells, and pencil cells. "
                    "Perls Prussian blue staining of the bone marrow shows absent iron stores.",
            "source": "Tietz textbook"
        },
        {
            "text": "Malaria diagnosis requires microscopic examination of Giemsa-stained "
                    "thick and thin blood films. Plasmodium falciparum shows multiple ring "
                    "forms per RBC, banana-shaped gametocytes, and Maurer's clefts. "
                    "Plasmodium vivax shows enlarged RBCs with Schüffner dots and ameboid "
                    "trophozoites. Rapid diagnostic tests (RDTs) detect HRP2 and pLDH antigens.",
            "source": "Henry's clinical diagnosis"
        },
        {
            "text": "The automated hematology analyser performs complete blood count (CBC) "
                    "with 5-part differential using impedance and light scattering. "
                    "The flow cytometer uses forward scatter (cell size), side scatter "
                    "(granularity), and fluorescence (DNA content) for immunophenotyping. "
                    "Quality control is performed daily using commercial control materials.",
            "source": "Hoffbrand's haematology"
        },
    ]

    print("=" * 60)
    print("  Entity Extraction Demo")
    print("=" * 60)

    # Extract entities from sample texts
    for item in sample_texts:
        print(f"\n--- Source: {item['source']} ---")
        entities = ext.extract_entities_from_text(item["text"], item["source"])
        relationships = ext.extract_relationships(item["text"], item["source"])

        print(f"  Entities found: {len(entities)}")
        for e in entities[:5]:
            print(f"    [{e['category']}] {e['name']}")

        print(f"  Relationships found: {len(relationships)}")
        for r in relationships[:3]:
            print(f"    {r['source']} --[{r['type']}]--> {r['target']}")

    # Save index
    ext._save_index()
    print(f"\n  Total index: {len(ext.entities)} entities, {len(ext.relationships)} relationships")

    # Search demo
    print("\n" + "=" * 60)
    print("  Search Demo")
    print("=" * 60)

    queries = ["ferritin", "malaria", "flow cytometer", "anemia", "giemsa"]
    for q in queries:
        results = ext.search_entities(q)
        if results:
            print(f"\n  Query: '{q}'")
            for r in results[:3]:
                print(f"    [{r['category']}] {r['name']} (score: {r['score']:.1f})")

    # Relationship traversal demo
    print("\n" + "=" * 60)
    print("  Relationship Traversal Demo")
    print("=" * 60)

    entity = "iron deficiency anemia"
    related = ext.get_related_entities(entity)
    if related:
        print(f"\n  Entities related to '{entity}':")
        for r in related[:5]:
            print(f"    {r['source']} --[{r['type']}]--> {r['target']}")

    # Context retrieval demo
    print("\n" + "=" * 60)
    print("  Context Retrieval Demo")
    print("=" * 60)

    context = ext.get_entity_context("ferritin")
    if context:
        print(f"\n{context}")

    print("\n  Done!")


if __name__ == "__main__":
    asyncio.run(demo())
