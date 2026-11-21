# -*- coding: utf-8 -*-
"""
Medical Entity Extraction Pipeline (Prototype)
Extracts structured entities from knowledge base chunks and builds
a lightweight relationship index for enhanced RAG retrieval.
"""
import json
import os
import asyncio
from typing import List, Dict, Any, Optional
from logging_config import get_logger

logger = get_logger(__name__)

# Entity categories relevant to clinical laboratory science
ENTITY_CATEGORIES = {
    "DISEASE": "Diseases, conditions, diagnoses",
    "TEST": "Laboratory tests, panels, assays",
    "CELL": "Cell types, morphological features",
    "EQUIPMENT": "Instruments, analysers, devices",
    "PROCEDURE": "Lab procedures, techniques, methods",
    "SUBSTANCE": "Chemicals, reagents, stains, biomarkers",
    "VALUE": "Reference ranges, cutoff values, thresholds",
    "PARASITE": "Parasites, life stages, morphology",
}

# Relationship types between entities
RELATIONSHIP_TYPES = {
    "DIAGNOSES": "Disease → confirmed by → Test",
    "MEASURES": "Test → measures → Substance/Biomarker",
    "PRODUCES": "Equipment → performs → Test",
    "STAINS_WITH": "Cell/Parasite → visualized by → Substance (stain)",
    "INDICATES": "Finding → suggests → Disease",
    "DIFFERENTIAL": "Disease → differential with → Disease",
    "STAGE_OF": "Parasite stage → belongs to → Parasite species",
    "REFERENCE": "Test → has reference range → Value",
    "CAUSED_BY": "Disease → caused by → Agent/Condition",
    "TREATED_BY": "Disease → treated by → Drug/Procedure",
    "ASSOCIATED_WITH": "Entity → associated with → Entity",
}


class EntityExtractor:
    """
    Extracts medical entities from text chunks using pattern matching + LLM.
    Builds a lightweight entity index for enhanced retrieval.
    """

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            from config import ENTITY_INDEX_PATH
            storage_path = ENTITY_INDEX_PATH
        self.storage_path = storage_path
        self.entities: Dict[str, Dict] = {}  # entity_id → entity_data
        self.relationships: List[Dict] = []
        self._load_index()

    def _load_index(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.entities = data.get("entities", {})
                    self.relationships = data.get("relationships", [])
                    logger.info(f"Loaded {len(self.entities)} entities, {len(self.relationships)} relationships")
            except Exception as e:
                logger.error(f"Failed to load entity index: {e}")

    def _save_index(self):
        try:
            tmp_path = f"{self.storage_path}.tmp.{os.getpid()}"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "entities": self.entities,
                    "relationships": self.relationships
                }, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.storage_path)
        except Exception as e:
            logger.error(f"Failed to save entity index: {e}")

    def extract_entities_from_text(self, text: str, source: str = "") -> List[Dict]:
        """
        Extract medical entities from a text chunk using pattern matching.
        Returns list of entity dicts with category, name, and metadata.
        """
        entities = []
        text_lower = text.lower()

        # Pattern-based extraction for common medical entities
        patterns = self._get_patterns()
        for category, term_list in patterns.items():
            for term in term_list:
                if term.lower() in text_lower:
                    entity_id = f"{category}:{term.lower()}"
                    if entity_id not in self.entities:
                        self.entities[entity_id] = {
                            "category": category,
                            "name": term,
                            "sources": [],
                            "context_snippets": []
                        }
                    entity = self.entities[entity_id]
                    if source and source not in entity["sources"]:
                        entity["sources"].append(source)
                    # Store a context snippet (100 chars around the match)
                    idx = text_lower.find(term.lower())
                    start = max(0, idx - 50)
                    end = min(len(text), idx + len(term) + 50)
                    snippet = text[start:end].strip()
                    if snippet and len(entity["context_snippets"]) < 5:
                        entity["context_snippets"].append(snippet)
                    entities.append(entity)

        return entities

    def extract_relationships(self, text: str, source: str = "", page: str = "") -> List[Dict]:
        """
        Extract relationships between entities from text using pattern matching.
        Enhanced with comprehensive medical relationship patterns.
        Includes page references for citation.
        """
        import re
        relationships = []
        text_lower = text.lower()

        # Comprehensive relationship patterns
        disease_test_patterns = [
            # DIAGNOSES: Disease → confirmed by → Test
            (r"(\w[\w\s]+?)\s+(?:is|are)\s+confirmed\s+by\s+([\w\s]+)", "DIAGNOSES"),
            (r"(\w[\w\s]+?)\s+(?:diagnosed\s+with|diagnosis\s+of)\s+([\w\s]+)", "DIAGNOSES"),
            (r"diagnosis\s+of\s+([\w\s]+?)\s+(?:is\s+)?(?:made\s+by|confirmed\s+by|requires)\s+([\w\s]+)", "DIAGNOSES"),
            (r"([\w\s]+?)\s+(?:is|are)\s+(?:diagnosed|confirmed)\s+(?:by|with)\s+([\w\s]+)", "DIAGNOSES"),

            # MEASURES: Test → measures → Substance
            (r"([\w\s]+?)\s+(?:test|assay|panel)\s+(?:for|of|detecting|measuring)\s+([\w\s]+)", "MEASURES"),
            (r"([\w\s]+?)\s+(?:measures|detects|quantifies|determines)\s+([\w\s]+)", "MEASURES"),
            (r"(?:serum|plasma|blood)\s+([\w\s]+?)\s+(?:level|concentration|amount)\s+(?:of\s+)?([\w\s]+)", "MEASURES"),

            # INDICATES: Finding → suggests → Disease
            (r"([\w\s]+?)\s+(?:is|are)\s+(?:elevated|increased|decreased|low|high)\s+in\s+([\w\s]+)", "INDICATES"),
            (r"([\w\s]+?)\s+(?:suggests?|indicates?|consistent\s+with|indicative\s+of)\s+([\w\s]+)", "INDICATES"),
            (r"(?:elevated|increased|decreased|low|high)\s+([\w\s]+?)\s+(?:is\s+)?(?:seen\s+in|found\s+in|associated\s+with)\s+([\w\s]+)", "INDICATES"),

            # STAINS_WITH: Cell/Parasite → visualized by → Stain
            (r"([\w\s]+?)\s+(?:is|are)\s+(?:visualized|stained|seen|identified)\s+(?:with|by|using)\s+([\w\s]+)", "STAINS_WITH"),
            (r"([\w\s]+?)\s+(?:stain|staining)\s+(?:reveals?|shows?|demonstrates?)\s+([\w\s]+)", "STAINS_WITH"),
            (r"(?:giemsa|wright|gram|pas|mpo| Sudan black|prussian blue)\s+(?:stain\s+)?(?:shows?|reveals?|demonstrates?)\s+([\w\s]+)", "STAINS_WITH"),

            # CAUSED_BY: Disease → caused by → Agent
            (r"([\w\s]+?)\s+(?:is|are)\s+caused\s+by\s+([\w\s]+)", "CAUSED_BY"),
            (r"([\w\s]+?)\s+(?:results?|resulting)\s+from\s+([\w\s]+)", "CAUSED_BY"),
            (r"(?:etiology|cause|agent)\s+(?:of\s+)?([\w\s]+?)\s+(?:is|are)\s+([\w\s]+)", "CAUSED_BY"),

            # STAGE_OF: Stage → belongs to → Species
            (r"([\w\s]+?)\s+(?:stage|form|phase)\s+(?:of\s+(?:the\s+)?)?([\w\s]+)", "STAGE_OF"),
            (r"(?:ring|trophozoite|schizont|gametocyte|merozoite)\s+(?:stage\s+)?(?:of\s+)?([\w\s]+)", "STAGE_OF"),

            # DIFFERENTIAL: Disease ↔ differential → Disease
            (r"(?:differential|differentials?)\s+(?:diagnosis|diagnoses)\s+(?:of\s+)?([\w\s]+?)\s+(?:includes?|are|is)\s+([\w\s]+)", "DIFFERENTIAL"),
            (r"([\w\s]+?)\s+(?:must\s+be\s+ruled\s+out|differential)\s+(?:for|of)\s+([\w\s]+)", "DIFFERENTIAL"),

            # REFERENCE: Test → reference range → Value
            (r"(?:normal|reference)\s+(?:range|values?|interval)\s+(?:for\s+)?([\w\s]+?)\s+(?:is|are)\s+([\d\s\-\.\/x]+[\w\/\.]*)", "REFERENCE"),
            (r"([\w\s]+?)\s+(?:normal|reference)\s+(?:range|values?):\s*([\d\s\-\.\/x]+[\w\/\.]*)", "REFERENCE"),

            # TREATED_BY: Disease → treated by → Drug
            (r"([\w\s]+?)\s+(?:is|are)\s+treated\s+(?:with|by)\s+([\w\s]+)", "TREATED_BY"),
            (r"(?:treatment|therapy)\s+(?:of\s+)?([\w\s]+?)\s+(?:includes?|involves?|uses?)\s+([\w\s]+)", "TREATED_BY"),
        ]

        for pattern, rel_type in disease_test_patterns:
            for match in re.finditer(pattern, text_lower):
                try:
                    source_entity = match.group(1).strip()
                    target_entity = match.group(2).strip()
                except IndexError:
                    continue  # Skip patterns with mismatched groups
                # Filter out very short or very long matches
                if 3 <= len(source_entity) <= 80 and 3 <= len(target_entity) <= 80:
                    relationships.append({
                        "type": rel_type,
                        "source": source_entity,
                        "target": target_entity,
                        "context": text[max(0, match.start()-30):min(len(text), match.end()+30)],
                        "source_doc": source,
                        "page": page
                    })

        return relationships

    def search_entities(self, query: str, category: str = None, top_k: int = 5) -> List[Dict]:
        """
        Search entities by name similarity. Lightweight alternative to vector search.
        """
        query_lower = query.lower()
        results = []

        for entity_id, entity in self.entities.items():
            if category and entity["category"] != category:
                continue
            name_lower = entity["name"].lower()
            # Simple scoring: exact match > contains > partial
            score = 0
            if query_lower == name_lower:
                score = 1.0
            elif query_lower in name_lower or name_lower in query_lower:
                score = 0.7
            elif any(w in name_lower for w in query_lower.split() if len(w) > 3):
                score = 0.4

            if score > 0:
                results.append({**entity, "score": score, "id": entity_id})

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_related_entities(self, entity_name: str, relationship_type: str = None) -> List[Dict]:
        """
        Find entities related to a given entity through relationships.
        """
        related = []
        name_lower = entity_name.lower()

        for rel in self.relationships:
            if rel["source"].lower() == name_lower or rel["target"].lower() == name_lower:
                if relationship_type is None or rel["type"] == relationship_type:
                    related.append(rel)

        return related

    def get_entity_context(self, entity_name: str) -> str:
        """
        Get context snippets for an entity — useful for prompt injection.
        Includes page references for citation.
        """
        entity_id = None
        for eid, e in self.entities.items():
            if e["name"].lower() == entity_name.lower():
                entity_id = eid
                break

        if not entity_id:
            return ""

        entity = self.entities[entity_id]
        snippets = entity.get("context_snippets", [])
        if not snippets:
            return ""

        # Get related relationships with page refs
        related = self.get_related_entities(entity_name)
        rel_lines = []
        for r in related[:5]:
            page_ref = f" (p.{r['page']})" if r.get('page') else ""
            rel_lines.append(f"  {r['type']}: {r['source']} → {r['target']}{page_ref}")

        result = f"Related context for '{entity['name']}':\n"
        result += "\n".join(f"- {s}" for s in snippets[:3])
        if rel_lines:
            result += "\n\nConnections:\n" + "\n".join(rel_lines)

        return result

    def build_index_from_chunks(self, chunks: List[Dict], source: str = ""):
        """
        Build entity index from knowledge base chunks.
        chunks: list of {"content": str, "metadata": dict}
        """
        logger.info(f"Building entity index from {len(chunks)} chunks...")
        all_entities = 0
        all_relationships = 0

        for i, chunk in enumerate(chunks):
            content = chunk.get("content", "") or chunk.get("page_content", "")
            if not content:
                continue

            # Extract page reference from metadata
            metadata = chunk.get("metadata", {})
            page = str(metadata.get("page", ""))

            entities = self.extract_entities_from_text(content, source)
            relationships = self.extract_relationships(content, source, page)
            all_entities += len(entities)
            all_relationships += len(relationships)

            # Store relationships (deduplicate by source+target+type)
            for rel in relationships:
                rel_key = f"{rel['type']}:{rel['source']}:{rel['target']}"
                if not any(f"{r['type']}:{r['source']}:{r['target']}" == rel_key for r in self.relationships):
                    self.relationships.append(rel)

            if (i + 1) % 100 == 0:
                logger.info(f"  Processed {i+1}/{len(chunks)} chunks...")

        self._save_index()
        logger.info(f"Entity index built: {len(self.entities)} unique entities, {len(self.relationships)} relationships "
                     f"(from {all_entities} mentions, {all_relationships} relation mentions)")

    def _get_patterns(self) -> Dict[str, List[str]]:
        """Return pattern lists for each entity category."""
        return {
            "DISEASE": [
                "anemia", "iron deficiency anemia", "thalassemia", "sickle cell disease",
                "megaloblastic anemia", "aplastic anemia", "hemolytic anemia",
                "leukemia", "acute lymphoblastic leukemia", "acute myeloid leukemia",
                "chronic lymphocytic leukemia", "chronic myeloid leukemia",
                "lymphoma", "hodgkin lymphoma", "non-hodgkin lymphoma",
                "multiple myeloma", "myelodysplastic syndrome",
                "thrombocytopenia", "thrombocytosis", "leukocytosis", "leukopenia",
                "neutropenia", "lymphocytosis", "monocytosis",
                "malaria", " babesiosis", "toxoplasmosis", "leishmaniasis",
                "urinary tract infection", "kidney stone", "diabetes mellitus",
                "liver disease", "hepatitis", "cirrhosis",
                "kidney disease", "renal failure", "chronic kidney disease",
                "coagulation disorder", "DIC", "disseminated intravascular coagulation",
                "sLE", "systemic lupus erythematosus", "rheumatoid arthritis",
                "crohn disease", "ulcerative colitis", "celiac disease",
                "hypothyroidism", "hyperthyroidism",
                "iron overload", "hemochromatosis", "wilson disease",
                "g6pd deficiency", "glucose-6-phosphate dehydrogenase deficiency",
                "hereditary spherocytosis", "elliptocytosis",
                "paroxysmal nocturnal hemoglobinuria", "pnh",
                "essential thrombocythemia", "polycythemia vera",
                "primary myelofibrosis", "mastocytosis",
            ],
            "TEST": [
                "complete blood count", "cbc", "full blood count", "fbc",
                "differential count", "white blood cell count", "wbc count",
                "red blood cell count", "rbc count", "hemoglobin", "hematocrit",
                "mean corpuscular volume", "mcv", "mean corpuscular hemoglobin", "mch",
                "mean corpuscular hemoglobin concentration", "mchc",
                "red cell distribution width", "rdw",
                "platelet count", "reticulocyte count", "erythrocyte sedimentation rate", "esr",
                "c-reactive protein", "crp", "procalcitonin",
                "iron studies", "serum iron", "ferritin", "transferrin", "tibc",
                "transferrin saturation", "serum folate", "vitamin b12",
                "serum creatinine", "blood urea nitrogen", "bun", "egfr",
                "liver function tests", "lft", "alt", "ast", "alp", "bilirubin",
                "albumin", "total protein",
                "coagulation profile", "pt", "inr", "aptt", "fibrinogen",
                "d-dimer", "fibrin degradation products", "fdp",
                "hba1c", "glycated hemoglobin", "fasting glucose",
                "lipid profile", "cholesterol", "triglycerides", "hdl", "ldl",
                "thyroid function tests", "tsh", "free t4", "free t3",
                "urinalysis", "urine microscopy", "urine culture",
                "bone marrow biopsy", "bone marrow aspiration",
                "peripheral blood smear", "blood film",
                "flow cytometry", "immunophenotyping",
                "cytogenetics", "fish", "pcr", "rt-pcr",
                "ldh", "uric acid", "haptoglobin", "methemoglobin",
                "hemoglobin electrophoresis", "hemoglobin hplc",
                "direct antiglobulin test", "dat", "coombs test",
                " indirect antiglobulin test", "iat",
                "prothrombin time", "activated partial thromboplastin time",
                "bleeding time", "clotting time",
                "esr", "sedimentation rate",
                "stool examination", "stool culture", "ova and parasites",
                "sputum culture", "acid-fast bacilli", "afb",
            ],
            "CELL": [
                "neutrophil", "lymphocyte", "monocyte", "eosinophil", "basophil",
                "blast", "promyelocyte", "myelocyte", "metamyelocyte", "band cell",
                "segmented neutrophil", "polymorphonuclear",
                "red blood cell", "erythrocyte", "reticulocyte", "nucleated rbc",
                "platelet", "thrombocyte", "megakaryocyte",
                "plasma cell", "fibroblast", "macrophage", "histiocyte",
                "sideroblast", "siderocyte", "target cell", "spherocyte",
                "schistocyte", "echinocyte", "acanthocyte", "elliptocyte",
                "teardrop cell", "dacrocyte", "stomatocyte",
                "howell-jolly body", "pappenheimer body", "basophilic stippling",
                "heinz body", "dohle body", "auer rod",
                "pelger-huet anomaly", "smudge cell", "basket cell",
                "atypical lymphocyte", "reactive lymphocyte", "downey cell",
                "lantern cell", "ring stage", "trophozoite", "schizont",
                "gametocyte", "merozoite", "tachyzoite", "bradyzoite",
                "ameboid form", "cyst form", "trophozoite form",
                "squamous epithelial cell", "transitional epithelial cell",
                "renal tubular epithelial cell", "oval fat body",
                "hyaline cast", "granular cast", "waxy cast", "fatty cast",
                "rb cast", "wbc cast", "muddy brown cast",
                "calcium oxalate", "uric acid crystal", "triple phosphate",
                "calcium phosphate", "cystine crystal",
                "candida", "yeast", "hyphae",
                "trichomonas", "enterobius", "strongyloides",
            ],
            "EQUIPMENT": [
                "autoanalyzer", "auto analyser", "hematology analyser",
                "chemistry analyser", "immunoassay analyser",
                "flow cytometer", "flow cytometry", "cytometer",
                "centrifuge", "microscope", "light microscope",
                "fluorescence microscope", "phase contrast microscope",
                "spectrophotometer", "coagulometer", "coagulation analyser",
                "blood gas analyser", "blood gas", "abg",
                "urine analyser", "sediment analyser",
                "pcr machine", "thermal cycler", "real-time pcr",
                "elisa reader", "microplate reader",
                "cell counter", "automated cell counter",
                "reticulocyte counter", "erythrocyte counter",
                "slide maker stainer", "automated stainer",
                "cytospin", "centrifuge", "incubator",
                "refrigerator", "freezer", "liquid nitrogen",
                "biosafety cabinet", "laminar flow hood",
                "质量控制", "quality control", "qc",
                "calibrator", "calibration", "control material",
            ],
            "PROCEDURE": [
                "staining", "wright stain", "giemsa stain", "gram stain",
                "acid-fast stain", "ziehl-neelsen stain", "perls prussian blue",
                "oil red o", "sudan black b", "periodic acid-schiff", "pas",
                "myeloperoxidase stain", "mpo", "nonspecific esterase",
                "chloroacetate esterase", "tartrate-resistant acid phosphatase", "trap",
                "immunohistochemistry", "immunofluorescence",
                "flow cytometry gating", "gating strategy",
                "cell counting", "manual differential", "automated differential",
                "bone marrow aspirate smear", "bone marrow trephine biopsy",
                "peripheral blood smear preparation", "blood film preparation",
                "buffy coat preparation", "plasma separation", "serum separation",
                "centrifugation", "incubation", "lysis", "fixation",
                "decalcification", "embedding", "sectioning", "mounting",
                "microscopic examination", "low power field", "high power field",
                "oil immersion field", "40x magnification", "100x magnification",
                "differential counting", "manual count", "automated count",
                "reticulocyte staining", "supravital staining",
                "mixing", "inversion", "eddlehoff tube",
            ],
            "SUBSTANCE": [
                "wright stain", "giemsa stain", "gram stain",
                "methylene blue", "crystal violet", "safranin",
                "india ink", "nigrosin", "brilliant cresyl blue",
                "prussian blue", "perls stain", "iron stain",
                "myeloperoxidase", "chloroacetate esterase",
                "hematoxylin", "eosin", "periodic acid-schiff",
                "ferritin", "transferrin", "hepcidin", "erythropoietin",
                "hemoglobin", "myoglobin", "bilirubin",
                "glucose", "cholesterol", "triglycerides",
                "creatinine", "urea", "uric acid",
                "albumin", "globulin", "fibrinogen",
                "d-dimer", "fibrin degradation products",
                "troponin", "ck-mb", "bnp", "nt-probnp",
                "psa", "afp", "hcg", "ca-125", "cea",
                "hba1c", "fructosamine",
                "heparin", "edta", "citrate", "fluoride",
                "reagent", "buffer", "diluent", "lysing solution",
                "wash solution", "cleaning solution",
            ],
            "VALUE": [
                "reference range", "normal range", "reference interval",
                "12-16 g/dl", "13.5-17.5 g/dl", "12-18 g/dl",
                "4.5-11 x 10^9/l", "4-11 x 10^9/l", "4.5-10.5 x 10^9/l",
                "150-400 x 10^9/l", "140-450 x 10^9/l",
                "80-100 fl", "78-100 fl", "80-96 fl",
                "27-33 pg", "27-31 pg",
                "32-36 g/dl", "31.5-35.5 g/dl",
                "0.5-1.5 mg/dl", "0.7-1.3 mg/dl",
                "5-20 mg/dl", "3-15 mg/dl",
                "70-100 mg/dl", "74-106 mg/dl",
                "20-200 u/l", "7-56 u/l", "10-40 u/l",
                "0.1-1.2 mg/dl", "0.2-1.0 mg/dl",
                "2.5-10 mg/l", "<5 mg/l", "<3 mg/l",
                "11-51 mm/h", "0-20 mm/h",
                "2.0-4.0%", "0.5-2.5%", "1-3%",
                "1000-4000/ul", "1500-8000/ul",
                "2.5-4.5 x 10^12/l", "4.0-5.5 x 10^12/l",
                "50-100 fl", "80-100 fl",
            ],
            "PARASITE": [
                "plasmodium falciparum", "plasmodium vivax",
                "plasmodium malariae", "plasmodium ovale",
                "plasmodium knowlesi",
                "babesia", "babesia microti", "babesia divergens",
                "trypanosoma", "trypanosoma brucei", "trypanosoma cruzi",
                "leishmania", "leishmania donovani", "leishmania major",
                "toxoplasma gondii", "toxoplasma",
                "entamoeba histolytica", "entamoeba coli",
                "giardia lamblia", "giardia duodenalis",
                "cryptosporidium", "cyclospora", "isospora",
                "strongyloides stercoralis",
                "ascaris lumbricoides",
                "trichuris trichiura", "whipworm",
                "hookworm", "ancylostoma", "necator",
                "enterobius vermicularis", "pinworm",
                "schistosoma", "schistosoma mansoni", "schistosoma haematobium",
                "schistosoma japonicum",
                "taenia", "taenia solium", "taenia saginata",
                "echinococcus", "hydatid cyst",
                "hymenolepis nana", "dwarf tapeworm",
                "diphyllobothrium latum", "fish tapeworm",
                "fasciola hepatica", "liver fluke",
                "clonorchis sinensis", "opisthorchis",
                "paragonimus", "lung fluke",
                "microsporidium", "enterocytozoon",
                "trichomonas vaginalis",
                "balantidium coli",
                "naegleria fowleri", "acanthamoeba",
            ],
        }


# Singleton
_entity_extractor = None

def get_entity_extractor() -> EntityExtractor:
    global _entity_extractor
    if _entity_extractor is None:
        _entity_extractor = EntityExtractor()
    return _entity_extractor
