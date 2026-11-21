import os
import sys
import pickle
from langchain_community.vectorstores import FAISS
from embeddings import MyGoogleEmbeddings

def test_load_faiss():
    index_dir = "brain_index"
    try:
        embeddings = MyGoogleEmbeddings(model="text-embedding-004")
        print("Embeddings loaded.")
        
        print("Attempting to load FAISS...")
        faiss_db = FAISS.load_local(
            folder_path=index_dir,
            embeddings=embeddings,
            index_name="index",
            allow_dangerous_deserialization=True
        )
        print(f"SUCCESS: FAISS loaded with {faiss_db.index.ntotal} vectors.")
        
    except Exception as e:
        print(f"FAILED TO LOAD FAISS: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_load_faiss()
