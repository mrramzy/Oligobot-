# -*- coding: utf-8 -*-
"""
Protocol Enforcer for OLIGOBOT V10
Acts as the 'Professor's Gatekeeper', enforcing the Diagnostic Protocol.
It ensures minimum required data is present before allowing a diagnostic query to proceed.
"""

import re
from typing import Dict, Tuple, Any

class ProtocolEnforcer:
    def __init__(self):
        # Regex patterns for entity extraction
        self.patterns = {
            "age": [
                r"(\d+)\s*(?:ساله|year|y/o|yo|yrs)",
                r"age\s*[:=]?\s*(\d+)",
                r"سن\s*[:=]?\s*(\d+)"
            ],
            "gender": [
                r"(?:آقا|مرد|پسر|male|man|boy|M)",
                r"(?:خانم|زن|دختر|female|woman|girl|F)"
            ]
        }

    def extract_entities(self, text: str) -> Dict[str, Any]:
        """Extracts basic entities (Age, Gender) using regex."""
        updates = {}
        
        # Extract Age
        for pattern in self.patterns["age"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    updates["patient_age"] = int(match.group(1))
                    break
                except ValueError:
                    pass

        # Extract Gender
        for pattern in self.patterns["gender"]:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                g_term = match.group(0).lower()
                if any(x in g_term for x in ["آقا", "مرد", "پسر", "male", "man", "boy", "m"]):
                    updates["patient_gender"] = "Male"
                else:
                    updates["patient_gender"] = "Female"
                break
        
        return updates

    def validate_diagnostic_request(self, case_data: Dict) -> Tuple[bool, str]:
        """
        The Gatekeeper Logic from diagnostic_protocol.md (Section 2).
        Checks if minimum required data (Age, Gender) is present for a diagnostic query.
        Returns (is_allowed_to_proceed, rejection_message).
        """
        missing = []
        if not (case_data and case_data.get("patient_age")):
            missing.append("سن بیمار (Age)")
        if not (case_data and case_data.get("patient_gender")):
            missing.append("جنسیت (Gender)")
            
        if missing:
            msg = (
                "✋ **پروتکل تشخیصی فعال شد!**\n\n"
                "برای تفسیر دقیق این کیس، طبق پروتکل به اطلاعات زیر نیاز دارم:\n"
                f"❌ **{', '.join(missing)}**\n\n"
                "لطفاً این موارد را بفرمایید تا تحلیل را شروع کنم."
            )
            return False, msg
            
        return True, ""

# Singleton
protocol_enforcer = ProtocolEnforcer()