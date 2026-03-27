import os
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv("E:/1-workspace/Google/Antigravity/edcat_v2/.env")

embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
CHROMA_PATH = "E:/1-workspace/Google/Antigravity/edcat_v2/edcat_root/resources/chroma_db"
try:
    vector_store = Chroma(
        collection_name="Jung_Individuacao",
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH,
    )
    docs = vector_store.get()
    print("Document count:", len(docs['ids']))
    print("Collections:", vector_store._client.list_collections())
except Exception as e:
    print("Error:", e)
