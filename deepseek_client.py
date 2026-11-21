# -*- coding: utf-8 -*-
"""
DeepSeek API Client
For using DeepSeek API as a third option
"""
import os
from typing import Optional, List, Dict, Any
import asyncio
from exceptions import ConfigError, DeepSeekAPIError
from retry_utils import deepseek_retry


class DeepSeekClient:
    """DeepSeek API Client for chat and embeddings"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize DeepSeek client
        
        Args:
            api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ConfigError("DEEPSEEK_API_KEY not set!", key="DEEPSEEK_API_KEY")
        
        # Try to import from openai library (DeepSeek compatible)
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.deepseek.com"
            )
        except ImportError:
            raise ConfigError("openai library required for DeepSeek. Install: pip install openai", key="openai")
    
    @deepseek_retry
    async def chat_completion_stream(self, messages: List[Dict[str, str]],
                                     model: str = "deepseek-chat",
                                     temperature: float = 0.7,
                                     max_tokens: int = 2000):
        """
        Send streaming chat completion request to DeepSeek.
        Yields text chunks as they arrive.
        """
        try:
            stream = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise DeepSeekAPIError(f"DeepSeek Streaming Error: {e}", cause=e)

    @deepseek_retry
    async def chat_completion(self, messages: List[Dict[str, str]],
                              model: str = "deepseek-chat",
                              temperature: float = 0.7,
                              max_tokens: int = 2000) -> str:
        """
        Send chat completion request to DeepSeek
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (default: deepseek-chat)
            temperature: Response creativity (0.0-1.0)
            max_tokens: Max response length
            
        Returns:
            Response text
        """
        try:
            response = await asyncio.to_thread(
                lambda: self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=False
                )
            )
            return response.choices[0].message.content
        except Exception as e:
            raise DeepSeekAPIError(f"DeepSeek API Error: {e}", cause=e)
    
    @deepseek_retry
    async def create_embedding(self, text: str, 
                               model: str = "deepseek-embedding") -> List[float]:
        """
        Create embedding for text using DeepSeek
        
        Args:
            text: Text to embed
            model: Embedding model name
            
        Returns:
            Embedding vector
        """
        try:
            # Note: DeepSeek might not have embedding endpoint yet
            # Using alternative approach or OpenAI-compatible endpoint
            response = await asyncio.to_thread(
                lambda: self.client.embeddings.create(
                    model=model,
                    input=text
                )
            )
            return response.data[0].embedding
        except Exception as e:
            from logging_config import get_logger
            logger = get_logger(__name__)
            logger.warning(f"DeepSeek Embedding Error: {e}")
            return []
    
    async def create_embeddings_batch(self, texts: List[str],
                                      model: str = "deepseek-embedding") -> List[List[float]]:
        """
        Create embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            model: Embedding model name
            
        Returns:
            List of embedding vectors
        """
        embeddings = []
        for text in texts:
            try:
                embedding = await self.create_embedding(text, model)
                embeddings.append(embedding)
            except Exception as e:
                print(f"⚠️ Error embedding text: {e}")
                embeddings.append([])
        return embeddings


# Test the client
if __name__ == "__main__":
    import sys
    
    async def test():
        try:
            client = DeepSeekClient()
            
            # Test chat
            print("Testing DeepSeek Chat...")
            response = await client.chat_completion([
                {"role": "user", "content": "سلام، تو چی؟"}
            ])
            print(f"✅ Chat Response: {response}\n")
            
            # Test embedding
            print("Testing DeepSeek Embedding...")
            embedding = await client.create_embedding("سلام دنیا")
            print(f"✅ Embedding dimension: {len(embedding)}\n")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            sys.exit(1)
    
    asyncio.run(test())
