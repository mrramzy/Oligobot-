
# -*- coding: utf-8 -*-
"""
Oligosoft Clinical RAG - Vision Module (v1.0)

Handles the creation and querying of the multi-modal image vector database.
This module gives the RAG system its "eyes," allowing it to perform
image-similarity searches across the entire library of atlases.

Core Components:
1.  **Image Embedding:** Uses a multi-modal model (CLIP) to convert images
    into numerical vectors that represent their visual content.
2.  **Vector Storage:** Uses a dedicated ChromaDB instance to store these
    image vectors and their associated metadata.
3.  **Similarity Search:** Provides a class to find and retrieve visually
    similar images from the database.
"""
import os
from PIL import Image
import torch
from pathlib import Path
from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores import Chroma

# --- Configuration ---
ATLAS_DIR = "./knowledge_base/atlases"
VISION_CHROMA_PATH = "./chroma_vision"
# Using a multi-modal model capable of embedding both images and text
VISION_MODEL = "clip-ViT-B-32"

def _create_image_embedding_function():
    """Factory function to create the embedding model."""
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(VISION_MODEL, device=device)
    # The model's encode function expects a list of image paths or PIL Images.
    # We wrap it to match the expected signature for ChromaDB's embedding function.
    # This is a bit of a workaround to adapt SentenceTransformer for Chroma.
    def embed_images(image_paths):
        images = [Image.open(p) for p in image_paths]
        return model.encode(images)
    # This is a placeholder for document embedding, not used for images.
    def embed_documents(texts):
        return model.encode(texts)

    # Chroma expects an object with embed_documents and embed_query methods
    class CLIPEmbedder:
        def embed_documents(self, texts): # Texts are actually paths here
            return embed_images(texts)
        def embed_query(self, query): # Query is a path here
            return embed_images([query])[0]

    return CLIPEmbedder()

def build_image_db():
    """Scans the atlases directory, embeds all images, and stores them in ChromaDB."""
    print("\n--- 👁️ Building Image Vector Database ---")
    if not os.path.exists(ATLAS_DIR) or not os.listdir(ATLAS_DIR):
        print(f"Atlas directory is empty or missing: {ATLAS_DIR}")
        return

    image_paths = sorted([os.path.join(dp, f) for dp, dn, fn in os.walk(ATLAS_DIR) for f in fn if f.lower().endswith(('.png', '.jpg', '.jpeg'))])
    
    if not image_paths:
        print("No images found in the atlases directory.")
        return

    print(f"Found {len(image_paths)} images to process.")

    # The metadata for images is derived from their filenames
    # Example: `Heme_WBC_Fig12-5_Rodak_2022.jpg`
    metadatas = []
    for p in image_paths:
        stem = Path(p).stem
        parts = stem.split("_")
        try:
            metadatas.append({
                "domain": parts[0],
                "subdomain": parts[1],
                "figure_id": parts[2],
                "source": parts[3],
                "year": int(parts[4])
            })
        except IndexError:
            print(f"⚠️ Skipping image with invalid name format: {Path(p).name}")
            metadatas.append({}) # Add empty metadata to maintain list length

    embedding_function = _create_image_embedding_function()

    # ChromaDB needs content to be added, for images, the path is the content.
    db = Chroma.from_texts(
        texts=image_paths, 
        embedding=embedding_function, 
        metadatas=metadatas,
        persist_directory=VISION_CHROMA_PATH
    )
    db.persist()
    print(f"✅ Image database built: {len(image_paths)} images stored in {VISION_CHROMA_PATH}")

class ImageSearch:
    """A class to perform similarity searches on the image database."""
    def __init__(self):
        if not os.path.exists(VISION_CHROMA_PATH):
            raise FileNotFoundError(f"Image DB not found at {VISION_CHROMA_PATH}. Rebuild it first.")
        
        self.embedding_function = _create_image_embedding_function()
        self.db = Chroma(persist_directory=VISION_CHROMA_PATH, embedding_function=self.embedding_function)

    def search(self, image_path: str, k: int = 3):
        """Finds k most similar images to the given image path."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Query image not found: {image_path}")

        print(f"\n🔍 Searching for images similar to: {os.path.basename(image_path)}")
        
        # The query itself is the image path.
        # The embedding function will handle loading and embedding it.
        results = self.db.similarity_search_by_vector(
            embedding=self.embedding_function.embed_query(image_path),
            k=k
        )
        
        # Format results
        formatted_results = []
        for doc in results:
            meta = doc.metadata
            formatted_results.append({
                "path": doc.page_content, # The path is stored in page_content
                "source": meta.get("source"),
                "figure_id": meta.get("figure_id"),
                "domain": meta.get("domain")
            })

        return formatted_results

# --- Example Usage (for testing) ---
if __name__ == "__main__":
    # 1. To build the database:
    # build_image_db()

    # 2. To search (assuming DB is built and you have a query image):
    # try:
    #     search_tool = ImageSearch()
    #     # Create a dummy image file for testing if you don't have one
    #     dummy_image_path = "./knowledge_base/atlases/dummy_query.jpg"
    #     if not os.path.exists(dummy_image_path):
    #          from PIL import Image
    #          Image.new('RGB', (100, 100), color = 'red').save(dummy_image_path)

    #     similar_images = search_tool.search(dummy_image_path)
    #     print("\n🖼️ Top Similar Images Found:")
    #     for img in similar_images:
    #         print(f"  - Path: {img['path']}, Source: {img['source']}")
    # except FileNotFoundError as e:
    #     print(e)
    print("Vision module is ready. Use through the manager or an API.")
