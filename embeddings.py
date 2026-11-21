# -*- coding: utf-8 -*-
"""
Embeddings Engine - Provider-specific embeddings classes
"""
import os
import time
import requests
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.embeddings import Embeddings
from key_manager import KeyManager
from sentence_transformers import SentenceTransformer
from exceptions import EmbeddingError, ArvanAPIError, ConfigError


class MyOpenAIEmbeddings(Embeddings):
    """OpenAI Embeddings"""
    def __init__(self, model: str = "text-embedding-3-small"):
        from openai import OpenAI
        self.model = model
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for text in texts:
            try:
                response = self.client.embeddings.create(input=text, model=self.model)
                embeddings.append(response.data[0].embedding)
            except Exception as e:
                print(f"OpenAI Embedding Error: {e}")
                embeddings.append([])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        try:
            response = self.client.embeddings.create(input=text, model=self.model)
            return response.data[0].embedding
        except Exception as e:
            print(f"OpenAI Embedding Error: {e}")
            return []


# class MyGoogleEmbeddings(Embeddings):
#     """Google Gemini Embeddings"""
#     def __init__(self, model: str = "text-embedding-004"):
#         self.model = model
#         # دریافت اولین کلید معتبر از KeyManager
#         key_manager = KeyManager.get_instance()
#         current_key = key_manager.keys[key_manager.current_index] if key_manager.keys else os.getenv("GOOGLE_API_KEY", "").split(',')[0]
        
#         self._impl = GoogleGenerativeAIEmbeddings(
#             model=model,
#             google_api_key=current_key,
#             task_type="retrieval_query"
#         )

#     def embed_documents(self, texts: list[str]) -> list[list[float]]:
#         try:
#             return self._impl.embed_documents(texts)
#         except Exception as e:
#             print(f"❌ Google Embed Docs Error: {e}")
#             raise e

#     def embed_query(self, text: str) -> list[float]:
#         try:
#             return self._impl.embed_query(text)
#         except Exception as e:
#             if any(err in str(e).lower() for err in ["429", "quota", "resource_exhausted"]):
#                 print(f"⚠️ Quota exceeded in Embedding. Rotating key...")
#                 KeyManager.get_instance().rotate()
#                 time.sleep(1)
#                 new_key = KeyManager.get_instance().keys[KeyManager.get_instance().current_index]
#                 self._impl = GoogleGenerativeAIEmbeddings(
#                     model=self.model,
#                     google_api_key=new_key,
#                     task_type="retrieval_query"
#                 )
#                 return self._impl.embed_query(text)
            
#             print(f"❌ Embedding Error: {e}")
#             raise e


class MyGoogleEmbeddings(Embeddings):
    """Google Gemini Embeddings (REST API - Updated for gemini-embedding-001 with 768 MRL)"""
    # 🚀 نام مدل به مدل زنده و رسمی سال ۲۰۲۶ تغییر یافت
    def __init__(self, model: str = None):
        if model is None:
            from config import GEMINI_EMBEDDING_MODEL
            model = GEMINI_EMBEDDING_MODEL
        self.model = model
        self.api_url = f"https://generativelanguage.googleapis.com/v1/models/{self.model}:embedContent"
        
        keys_str = os.getenv("GOOGLE_API_KEY", "")
        self.google_keys = [k.strip() for k in keys_str.split(',') if k.strip()]
        self.current_key_index = 0
        self.current_key = self.google_keys[0] if self.google_keys else ""

    def _embed_text(self, text: str) -> list[float]:
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": f"models/{self.model}",
            "content": {"parts": [{"text": text}]},
            "taskType": "RETRIEVAL_QUERY",
            # 🎯 جادوی اصلی: مجبور کردن گوگل به تولید وکتور ۷۶۸ بعدی برای هماهنگی کامل با FAISS شما
            "outputDimensionality": 768
        }
        
        try:
            response = requests.post(f"{self.api_url}?key={self.current_key}", json=payload, headers=headers)
            
            if response.status_code == 200:
                return response.json().get("embedding", {}).get("values", [])
            
            elif response.status_code == 429 or "quota" in response.text.lower():
                print("⚠️ Quota exceeded for Google Embeddings. Rotating key locally...")
                if self.google_keys:
                    self.current_key_index = (self.current_key_index + 1) % len(self.google_keys)
                    self.current_key = self.google_keys[self.current_key_index]
                time.sleep(1)
                
                retry_response = requests.post(f"{self.api_url}?key={self.current_key}", json=payload, headers=headers)
                if retry_response.status_code == 200:
                    return retry_response.json().get("embedding", {}).get("values", [])
                else:
                    raise ArvanAPIError(f"Failed after rotation: {retry_response.text}", status_code=retry_response.status_code)
            else:
                raise ArvanAPIError(f"HTTP {response.status_code}: {response.text[:200]}", status_code=response.status_code)
        except Exception as e:
            print(f"❌ REST API Embed Error: {e}")
            raise e

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed_text(text)


class ArvanEmbeddings(Embeddings):
    """
    🧬 ArvanCloud AIaaS Embeddings (OpenAI-compatible /v1/embeddings).

    موتور اصلی امبدینگ RAG (پیش‌فرض: bge-m3 @ 1024).
    هم برای ساخت ایندکس (embed_documents با batch) و هم کوئری ربات (embed_query) استفاده می‌شود.
    پایدار (open-source) و بدون نیاز به سرور GPU — آروان مدل را میزبانی می‌کند.
    """
    def __init__(self, base_url: str = None, api_key: str = None,
                 model: str = None, batch_size: int = None):
        from config import (ARVAN_EMBEDDING_BASE_URL, ARVAN_API_KEY,
                            ARVAN_EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE)
        self.base_url = (base_url or ARVAN_EMBEDDING_BASE_URL).rstrip("/")
        self.api_key = api_key or ARVAN_API_KEY
        self.model = model or ARVAN_EMBEDDING_MODEL
        self.batch_size = batch_size or EMBEDDING_BATCH_SIZE
        if not self.base_url or not self.api_key:
            raise ConfigError(
                "ArvanEmbeddings: ARVAN_EMBEDDING_BASE_URL and ARVAN_API_KEY must be set in .env.",
                key="ARVAN_EMBEDDING_BASE_URL/ARVAN_API_KEY"
            )
        self.url = f"{self.base_url}/embeddings"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _post(self, inputs: list[str], max_retries: int = 4) -> list[list[float]]:
        """یک درخواست batch با retry/backoff نمایی."""
        payload = {"model": self.model, "input": inputs}
        last_err = None
        for attempt in range(max_retries):
            try:
                resp = requests.post(self.url, json=payload, headers=self.headers, timeout=120)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    # حفظ ترتیب ورودی بر اساس index
                    data = sorted(data, key=lambda d: d.get("index", 0))
                    return [d["embedding"] for d in data]
                # خطاهای موقت (rate limit / سرور) → retry
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_err = f"HTTP {resp.status_code}: {resp.text[:150]}"
                    time.sleep(2 ** attempt)
                    continue
                raise ArvanAPIError(f"Arvan embed HTTP {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)
            except requests.RequestException as e:
                last_err = str(e)
                time.sleep(2 ** attempt)
        raise ArvanAPIError(f"Arvan embedding failed after {max_retries} retries: {last_err}", status_code=None)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            out.extend(self._post(batch))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._post([text])[0]


class LocalEmbeddings(Embeddings):
    """Wrapper to make SentenceTransformer compatible with LangChain."""
    def __init__(self, model_name: str):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.model.encode(texts, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.model.encode([text], convert_to_numpy=True)[0].tolist()
    
    def __call__(self, text: str) -> list[float]:
        """Make the object callable to satisfy LangChain's expectations."""
        return self.embed_query(text)


def get_embeddings_model(ai_model: str) -> Embeddings:
    if ai_model == "openai":
        return MyOpenAIEmbeddings(model="text-embedding-3-small")
    elif ai_model == "gemini":
        from config import EMBEDDING_MODEL
        return MyGoogleEmbeddings(model=EMBEDDING_MODEL)
    return MyOpenAIEmbeddings(model="text-embedding-3-small")


def get_rag_embeddings() -> Embeddings:
    """
    🧬 منبع واحد امبدینگ RAG — هم ساخت ایندکس و هم کوئری ربات از این تابع می‌گیرند.
    این تضمین می‌کند مدلِ ساخت و کوئری همیشه یکی باشد (ریشه‌ی باگ قبلی همین ناهماهنگی بود).
    تعویض مدل در آینده = تغییر EMBEDDING_PROVIDER در .env.
    """
    from config import EMBEDDING_PROVIDER
    provider = EMBEDDING_PROVIDER
    if provider == "arvan":
        return ArvanEmbeddings()
    elif provider == "gemini":
        from config import GEMINI_EMBEDDING_MODEL
        return MyGoogleEmbeddings(model=GEMINI_EMBEDDING_MODEL)
    elif provider == "openai":
        return MyOpenAIEmbeddings(model="text-embedding-3-large")
    elif provider == "local":
        return LocalEmbeddings("BAAI/bge-m3")
    raise ConfigError(f"Unknown EMBEDDING_PROVIDER: {provider!r} (options: arvan/gemini/openai/local)", key="EMBEDDING_PROVIDER")