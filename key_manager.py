# -*- coding: utf-8 -*-
import os
import warnings
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=FutureWarning)
from logging_config import get_logger
logger = get_logger(__name__)
from exceptions import ConfigError
load_dotenv()

class KeyManager:
    """
    🔑 KeyManager - Multi-provider support (OpenAI + Gemini)
    
    ACTIVE: OpenAI (current)
    INACTIVE: Gemini (legacy - can be reactivated in .env)
    """
    
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        from config import PRIMARY_PROVIDER
        self.provider = PRIMARY_PROVIDER
        
        if self.provider == "openai":
            self._init_openai()
        elif self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "deepseek":
            self._init_deepseek()
        else:
            raise ConfigError(f"Unknown PRIMARY_PROVIDER: {self.provider}", key="PRIMARY_PROVIDER")
    
    def _init_openai(self):
        """Initialize OpenAI API"""
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.api_key:
            raise ConfigError("OPENAI_API_KEY not found! Please check .env file.", key="OPENAI_API_KEY")
        logger.info(f"✅ OpenAI initialized (Provider: {self.provider})")
        self.keys = [self.api_key]  # Single key for OpenAI
        self.current_index = 0
    
    def _init_gemini(self):
        """Initialize Gemini API with multiple key support"""
        from google import genai as google_genai
        
        keys_str = os.getenv("GOOGLE_API_KEY", "")
        self.keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        self.current_index = 0
        
        if not self.keys:
            raise ConfigError("No Gemini API Keys found! Please check .env file.", key="GOOGLE_API_KEY")
        
        logger.info(f"✅ Gemini initialized with {len(self.keys)} API keys")
        self.configure()
    
    def configure(self):
        """Configure current API key — no-op for new google.genai SDK (client-based)."""
        if self.provider == "gemini":
            current_key = self.keys[self.current_index]
            logger.info(f"🔑 Gemini Key #{self.current_index + 1} selected (client created on-demand)")
    
    def _init_deepseek(self):
        """Initialize DeepSeek API"""
        self.api_key = os.getenv("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise ConfigError("DEEPSEEK_API_KEY not found! Please check .env file.", key="DEEPSEEK_API_KEY")
        print(f"✅ DeepSeek initialized")
        self.keys = [self.api_key]
        self.current_index = 0
    
    def rotate(self):
        """Rotate to next API key (Gemini only)"""
        if self.provider != "gemini":
            logger.info(f"ℹ️ Key rotation not needed for {self.provider}")
            return None
        
        self.current_index = (self.current_index + 1) % len(self.keys)
        self.configure()
        logger.info(f"🔄 ROTATING GEMINI KEYS... Switched to Key #{self.current_index + 1}")
        return self.keys[self.current_index]

    def rotate_key(self):
        """Alias for rotate to match usage in other modules"""
        return self.rotate()