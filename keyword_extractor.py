# -*- coding: utf-8 -*-
"""
🔑 Advanced Keyword Extraction Engine
استخراج کلیدواژه‌های دقیق و قدرتمند برای بهبود جستجو در RAG
"""

import re
from typing import List, Optional

# --- Constants ---

MEDICAL_KEYWORDS = {
    'رنج': ['رنج', 'محدوده', 'range', 'بازه', 'طبیعی'],
    'نرمال': ['نرمال', 'طبیعی', 'normal', 'standard', 'معیار'],
    'بیمار': ['بیماری', 'ناخوشی', 'اختلال', 'disease', 'disorder'],
    'تشخیص': ['تشخیص', 'diagnosis', 'تشخیصی'],
    'درمان': ['درمان', 'treatment', 'تراپی', 'therapy'],
    'علائم': ['علامت', 'عارضه', 'symptom', 'sign', 'نشانه'],
    'آزمایش': ['آزمایش', 'تست', 'test', 'پاتولوژی', 'lab'],
    'خون': ['خون', 'رگ', 'blood', 'hemoglobin', 'RBC', 'WBC'],
    'کبد': ['کبد', 'liver', 'hepatic'],
    'کلیه': ['کلیه', 'kidney', 'renal'],
    'قلب': ['قلب', 'heart', 'cardiac'],
    'ریه': ['ریه', 'lung', 'pulmonary'],
    'معده': ['معده', 'stomach', 'gastric'],
    'موثر': ['موثر', 'مؤثر', 'effective', 'efficacy'],
    'غلظت': ['غلظت', 'concentration', 'level'],
    'عدد': ['عدد', 'نمره', 'score', 'count', 'value'],
    'عناصر': ['زینک', 'روی', 'zinc', 'مس', 'copper', 'آهن', 'اهن', 'iron', 'منیزیم', 'magnesium', 'سرب', 'lead'],
}

DOMAIN_SPECIFIC = [
    'طبیعی', 'نرمال', 'رنج نرمال', 'محدوده', 'معیار', 'مقادیر مرجع',
    'بالا', 'پایین', 'کم', 'زیاد', 'نقص', 'اضافه',
    'حد پایین', 'حد بالا', 'threshold', 'cutoff',
    'مقدار', 'میزان', 'درصد', 'نسبت', 'ratio',
    'interval', 'intervals', 'value', 'values', 'reference'
]

STOP_WORDS_FARSI = {
    'و', 'یا', 'در', 'به', 'از', 'است', 'این', 'آن', 'که', 'برای',
    'با', 'بدون', 'بر', 'اما', 'لی', 'پس', 'چه', 'نه', 'اگر', 'کنید',
    'شود', 'شدن', 'کردن', 'نمی', 'می', 'ایا', 'باید', 'توان', 'تا',
}

STOP_WORDS_ENGLISH = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'of', 'to', 'for',
    'is', 'was', 'are', 'be', 'been', 'have', 'has', 'had', 'do',
    'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
    'with', 'from', 'by', 'at', 'on', 'as', 'if', 'what', 'which',
    'who', 'when', 'where', 'why', 'how', 'this', 'that', 'these',
    'those', 'not', 'can', 'it', 'your', 'our', 'their',
}

COMMON_MEDICAL_SEARCHES = {
    'رنج نرمال': ['رنج نرمال', 'محدوده طبیعی', 'normal range', 'reference values', 'normal values'],
    'هموگلوبین': ['هموگلوبین', 'hemoglobin', 'hb', 'hgb', 'rbc', 'خون'],
    'گلوکز': ['گلوکز', 'glucose', 'قند', 'blood sugar'],
    'کلسترول': ['کلسترول', 'cholesterol', 'lipid', 'چربی'],
    'البومین': ['البومین', 'albumin', 'پروتئین', 'protein'],
    'پروتیین توتال': ['total protein', 'serum total protein', 'reference range total protein', 'پروتئین توتال'],
    'پروتئین توتال': ['total protein', 'serum total protein', 'reference range total protein'],
    'آنزیم': ['آنزیم', 'enzyme', 'ast', 'alt', 'alp'],
    'hdl': ['hdl', 'high density lipoprotein', 'alpha lipoprotein', 'hdl-c', 'کلسترول خوب'],
    'ldl': ['ldl', 'low density lipoprotein', 'beta lipoprotein', 'ldl-c', 'کلسترول بد'],
}

# --- Class Definition ---

class KeywordExtractor:
    """
    Encapsulates all logic for keyword extraction and query enrichment.
    This class is designed to be instantiated by the RAGSystem.
    """

    def enrich_query(self, original_query: str) -> List[str]:
        """
        Creates a list of enriched search queries from the original user input.
        This is the main public method for this class.
        """
        cached = self._apply_medical_cache(original_query)
        if cached:
            return cached
        
        return self._generate_search_prompts(original_query)

    def _apply_medical_cache(self, query: str) -> Optional[List[str]]:
        """Checks if the query matches a common medical topic."""
        query_lower = query.lower()
        for topic, variants in COMMON_MEDICAL_SEARCHES.items():
            if topic in query_lower:
                return variants
        return None

    def _generate_search_prompts(self, query: str) -> List[str]:
        """Generates multiple parallel search prompts for deeper exploration."""
        prompts = {query}
        
        entities = self._extract_medical_entities(query)
        prompts.update(entities)
        
        boosted = self._boost_specific_keywords(query, entities)
        prompts.update(boosted[:5])
        
        if any(term in query.lower() for term in ['رنج', 'محدوده', 'normal', 'range']):
            prompts.update(['رنج نرمال', 'محدوده طبیعی', 'normal range', 'reference values'])
        
        return list(filter(None, prompts))

    def _extract_medical_entities(self, query: str) -> List[str]:
        """Extracts medical entities from the query."""
        entities = []
        query_lower = query.lower()
        
        for keywords in MEDICAL_KEYWORDS.values():
            for keyword in keywords:
                if keyword in query_lower:
                    entities.append(keyword)
        
        words = re.split(r'\s+|,|\?', query)
        for word in words:
            word_clean = word.lower()
            if len(word_clean) >= 3 and word_clean not in STOP_WORDS_FARSI and word_clean not in STOP_WORDS_ENGLISH:
                if word_clean not in entities:
                    entities.append(word_clean)
        
        return list(dict.fromkeys(entities))

    def _boost_specific_keywords(self, query: str, entities: List[str]) -> List[str]:
        """Boosts important keywords for search."""
        boosted = []
        query_lower = query.lower()
        
        if 'رنج نرمال' in query_lower or 'محدوده طبیعی' in query_lower or 'normal range' in query_lower:
            boosted.extend(['رنج نرمال', 'normal range', 'محدوده طبیعی'])
        
        # ✅ DYNAMIC STRATEGY: Use the main dictionary instead of hardcoded list
        # Flatten all known medical keywords for fast lookup
        all_known_medical_terms = {term for sublist in MEDICAL_KEYWORDS.values() for term in sublist}

        for entity in entities:
            # If the entity is a known medical term defined in our dictionary, BOOST IT!
            if entity in all_known_medical_terms or entity in DOMAIN_SPECIFIC:
                boosted.append(entity)
        
        boosted.extend([e for e in entities if e not in boosted])
        
        return list(dict.fromkeys(boosted))

# --- Main execution for testing ---
if __name__ == "__main__":
    extractor = KeywordExtractor()
    test_queries = [
        "رنج نرمال هموگلوبین چیه",
        "محدوده طبیعی WBC در خون",
        "normal range for glucose",
        "کلسترول سالم برای بالغ",
    ]
    
    for q in test_queries:
        print(f"\n📝 Query: {q}")
        searches = extractor.enrich_query(q)
        print(f"   Search variants: {searches}")
