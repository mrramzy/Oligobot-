# -*- coding: utf-8 -*-
import os
import logging

class PromptManager:
    """Loads and manages all specialized prompts from the PSL directory."""
    def __init__(self, base_path: str):
        self.base_path = base_path
        self.prompts = {}
        self.loaded = False

    def load_prompts(self):
        """Reads all .md files from the specified directory into memory."""
        if self.loaded:
            return
        
        if not os.path.isdir(self.base_path):
            logging.error(f"[PromptManager] Error: Directory not found at '{self.base_path}'")
            return

        logging.info(f"[PromptManager] Loading prompts from: {self.base_path}")
        for filename in os.listdir(self.base_path):
            if filename.endswith(".md"):
                try:
                    # Key is the filename without extension, in uppercase (e.g., HEMATOLOGY)
                    key = filename[:-3].upper()
                    path = os.path.join(self.base_path, filename)
                    with open(path, "r", encoding="utf-8") as f:
                        self.prompts[key] = f.read()
                        logging.info(f"  ✅ Loaded prompt: {key}")
                except Exception as e:
                    logging.error(f"  ❌ Failed to load prompt from {filename}: {e}")
        
        self.loaded = True
        logging.info("[PromptManager] All prompts loaded.")

    def get_prompt(self, category: str) -> str | None:
        """Returns the content of a specific prompt file."""
        return self.prompts.get(category.upper())

    def get_all_prompts(self) -> dict:
        """Returns the entire dictionary of loaded prompts."""
        return self.prompts

    def prompt_exists(self, category: str) -> bool:
        """Checks if a prompt for a given category has been loaded."""
        return category.upper() in self.prompts
