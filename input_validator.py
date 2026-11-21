
# -*- coding: utf-8 -*-
"""
Input validation for security, using custom exceptions for clarity.
- Protects against prompt injection and malformed inputs.
- Uses the InvalidInputError for specific error handling.
"""

import re

# NEW: Import the custom exception we defined
from exceptions import InvalidInputError

class InputValidator:
    """Validates and sanitizes user inputs, raising specific exceptions on failure."""
    
    # --- Configuration Constants ---
    MAX_QUERY_LENGTH = 1000
    MAX_SPECIAL_CHAR_RATIO = 0.3 # Allow up to 30% non-alphanumeric characters
    
    # Regular expressions for detecting potentially malicious patterns
    INJECTION_PATTERNS = [
        # System-level commands or attempts to break out of the prompt context
        r'\[SYSTEM',
        r'execute\s*\(', 
        r'eval\s*\(', 
        r'__import__',
        r'subprocess',
        # Database-style attacks
        r'delete\s+from',
        r'drop\s+table',
        # Filesystem attacks
        r'rm\s+-r',
    ]

    # Basic physiological limits to detect nonsense inputs
    CLINICAL_RANGES = {
        'ph': (6.8, 7.8),
        'hgb': (2.0, 25.0), # Hemoglobin
        'k': (1.0, 10.0),   # Potassium
    }
    
    @classmethod
    def validate_query(cls, query: str):
        """
        Validates the main user query for security and format.

        Raises:
            InvalidInputError: If any validation check fails.
        """
        # 1. Check for empty or whitespace-only queries
        if not query or not query.strip():
            raise InvalidInputError("Query cannot be empty.")
        
        # 2. Check for excessive length
        if len(query) > cls.MAX_QUERY_LENGTH:
            raise InvalidInputError(
                f"Query exceeds maximum length of {cls.MAX_QUERY_LENGTH} characters."
            )
        
        # 3. Check for suspicious injection patterns
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                # Do not reveal the matched pattern to the user for security
                raise InvalidInputError("Query contains a suspicious pattern.")
        
        # 4. Check for an unusual ratio of special characters
        # This can be a sign of obfuscated attacks or garbage input
        # We ignore common Persian punctuation
        alnum_chars = sum(1 for c in query if c.isalnum())
        total_chars = len(query)
        if total_chars > 0 and (alnum_chars / total_chars) < (1 - cls.MAX_SPECIAL_CHAR_RATIO):
            raise InvalidInputError("Query contains an unusual amount of special characters.")

        # 5. Clinical Safety Check
        cls.validate_clinical_safety(query)

    @classmethod
    def validate_clinical_safety(cls, query: str):
        """Checks for clinically impossible values to prevent processing garbage data."""
        lower_query = query.lower()
        
        # Example: Check pH
        if 'ph' in lower_query:
            # Simple regex to find numbers near 'ph'
            matches = re.findall(r'ph\s*[:=]?\s*(\d+\.?\d*)', lower_query)
            for val in matches:
                f_val = float(val)
                if not (cls.CLINICAL_RANGES['ph'][0] <= f_val <= cls.CLINICAL_RANGES['ph'][1]):
                    raise InvalidInputError(f"مقدار pH وارد شده ({f_val}) با حیات سازگار نیست.")
    
    @classmethod
    def validate_user_id(cls, user_id: any):
        """
        Validates the user ID for correct type and value.

        Raises:
            InvalidInputError: If the user ID is not a positive integer.
        """
        if not isinstance(user_id, int) or user_id <= 0:
            raise InvalidInputError("User ID must be a positive integer.")
    
    @classmethod
    def sanitize_output(cls, text: str) -> str:
        """
        Sanitizes text received from the LLM to prevent it from rendering
        unwanted markdown or executable code snippets.
        
        This is the definitive, centralized cleaning function.
        """
        if not text:
            return ""
        
        # Step 0: Normalize Persian/Arabic numbers to English FIRST
        # This ensures regexes relying on \d work correctly and prevents RTL issues early
        persian_map = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
        text = text.translate(persian_map)
        
        # Step 1: Convert HTML-like tags to Markdown
        text = text.replace("<p>", "").replace("</p>", "\n")
        text = text.replace("<b>", "*").replace("</b>", "*")
        text = text.replace("<i>", "_").replace("</i>", "_")
        text = text.replace("<br>", "\n").replace("<br/>", "\n")
        text = text.replace("<strong>", "*").replace("</strong>", "*")
        text = text.replace("<em>", "_").replace("</em>", "_")
        
        # Step 2: Remove zero-width characters and other invisible chars
        text = re.sub(r'[\u200b\u200d\ufeff]+', '', text)
        
        # Step 3: Clean excess Markdown and code blocks
        text = text.replace("`", "'")
        text = text.replace("```", "")
        text = text.replace("###", "").replace("##", "").replace("#", "")
        text = re.sub(r'\*{3,}', '**', text)
        text = re.sub(r'_{3,}', '__', text)
        text = re.sub(r'(\*\*){2,}', '**', text)
        text = re.sub(r'(__){2,}', '__', text)
        
        # Step 4: Remove repetitive, boilerplate text
        text = text.replace('(سلول زنده)', '')
        text = text.replace('( سلول زنده )', '')
        
        # Step 5: Standardize punctuation spacing
        text = re.sub(r' +([,،.؛:؟!])', r'\1', text)
        # Add space after punctuation (excluding dot)
        text = re.sub(r'([،,؛:؟!])(?! )', r'\1 ', text)
        
        # ✅ FIX: Repair time format (e.g. "12: 30" -> "12:30") broken by punctuation rule
        text = re.sub(r'(?<=\d):\s+(?=\d)', ':', text)

        # Add space after dot, protecting decimal numbers (e.g. 13.5)
        # Case 1: Dot not preceded by digit (e.g. "word.Next")
        text = re.sub(r'(?<!\d)\.(?! )', '. ', text)
        # Case 2: Dot preceded by digit, but not followed by digit or space (e.g. "Item 1.Next")
        text = re.sub(r'(?<=\d)\.(?![\d\s])', '. ', text)
        text = re.sub(r' +', ' ', text)
        
        # Step 6: Standardize parentheses spacing
        text = re.sub(r'\( +', '(', text)
        text = re.sub(r' +\)', ')', text)
        text = re.sub(r'\)([^ .،:؛؟!])', r') \1', text)
        
        # Step 7: Smart bullet point processing
        lines = text.split('\n')
        formatted_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("- "):
                line = "• " + line[2:].strip()
            elif line.startswith("* "):
                line = "• " + line[2:].strip()
            formatted_lines.append(line)
        text = '\n'.join(formatted_lines)
        
        # Step 8: Smart Paragraph Spacing (Fix nested text)
        # Add double newline after periods/colons that end a line, if followed by text
        text = re.sub(r'(\.|:|!|\?)\n(?!\n)', r'\1\n\n', text)
        # Ensure bullet points have space above them if not already spaced
        text = re.sub(r'(?<!\n)\n([•\-\*])', r'\n\n\1', text)
        
        # Step 9: Fix RTL/LTR mixing issues for Telegram rendering
        # Add a Right-to-Left Mark (RLM) before lines starting with English/numeric
        # characters to preserve RTL layout, but only if the line also contains Persian.
        final_lines = []
        for line in text.split('\n'):
            # Check if a line starts with an LTR character but contains RTL characters
            if line.strip() and re.match(r'^[a-zA-Z0-9\(\[]', line.strip()) and re.search(r'[\u0600-\u06FF]', line):
                final_lines.append('\u200f' + line) # Prepend RLM character U+200F
            else:
                final_lines.append(line)
        
        return '\n'.join(final_lines).strip()

    @classmethod
    def validate_all(cls, user_id: any, query: str):
        """
        A convenient helper method to run all primary validations at once.
        """
        cls.validate_user_id(user_id)
        cls.validate_query(query)
