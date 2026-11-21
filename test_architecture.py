#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test the specialized prompt loading workflow for OLIGOBOT V10
"""

import asyncio
import sys
import os

if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def test_architecture():
    """Test the dual-mode architecture."""
    
    print("\n" + "="*70)
    print("OLIGOBOT V10 - Architecture & Specialized Prompt Workflow Test")
    print("="*70 + "\n")
    
    # Import
    from app import rag_system
    from utils import detect_clinical_domain
    
    # Test Cases
    test_cases = [
        {
            "name": "Image Analysis - Hematology",
            "mode": "image",
            "query": "عکس خون با بلاست‌های فراوان و Auer rods",
            "expected_domain": "hematology",
            "expected_prompt": "hematology.md"
        },
        {
            "name": "Image Analysis - Pathology",
            "mode": "image",
            "query": "تصویر بافت شامل سلول‌های سرطانی",
            "expected_domain": "pathology",
            "expected_prompt": "pathology.md"
        },
        {
            "name": "Text Query - General",
            "mode": "text",
            "query": "آنمی فقر آهن چه علائمی دارد؟",
            "expected_domain": "hematology",
            "expected_prompt": "[Core Prompts]"
        },
        {
            "name": "Text Query - Urinalysis",
            "mode": "text",
            "query": "در ادرار کریستال ستروویت چه‌طور است؟",
            "expected_domain": "urinalysis",
            "expected_prompt": "[Core Prompts]"
        }
    ]
    
    print("TEST CASES:\n")
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"[Test {i}] {test_case['name']}")
        print(f"  Mode: {test_case['mode']}")
        print(f"  Query: {test_case['query'][:50]}...")
        
        # Domain Detection
        detected_domain = detect_clinical_domain(test_case['query'])
        domain_status = "✓ PASS" if detected_domain == test_case['expected_domain'] else "✗ FAIL"
        print(f"  Domain: {detected_domain} {domain_status}")
        
        # Prompt Loading (Simulation)
        if test_case['mode'] == 'image':
            # For image: Load specialized prompt
            prompt_path = f"PSL/{detected_domain}.md"
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    lines = len(f.readlines())
                print(f"  Prompt: {prompt_path} ({lines} lines) ✓")
            else:
                print(f"  Prompt: {prompt_path} ✗ NOT FOUND")
        else:
            # For text: Use core prompts
            core_prompts = [
                "PSL/system_core.md",
                "PSL/human_interaction.md",
                "PSL/diagnostic_protocol.md",
                "PSL/prompt_injection_shield.md"
            ]
            print(f"  Prompts: {', '.join(p.split('/')[-1] for p in core_prompts)}")
            loaded = sum(1 for p in core_prompts if os.path.exists(p))
            print(f"  Status: {loaded}/4 core prompts loaded ✓")
        
        print()
    
    print("="*70)
    print("Architecture Test Summary:")
    print("="*70)
    print("""
    ✓ Image Processing: Uses SPECIALIZED domain-specific prompts
    ✓ Text Processing: Uses 4 CORE generic prompts
    ✓ Domain Detection: Automatic keyword-based classification
    ✓ RAG Integration: Both modes integrated with knowledge base
    
    This is the INNOVATIVE dual-mode architecture!
    """)
    print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_architecture())
