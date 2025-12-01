import os
from typing import List

import pandas as pd
import numpy as np
import faiss
from pydantic import BaseModel, Field

from ibm_watsonx_ai.foundation_models.schema import TextChatParameters
from langchain_ibm import ChatWatsonx, WatsonxEmbeddings

from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission


# --- CONFIG ---
WATSONX_APIKEY="WATSONX_APIKEY"
PROJECT_ID="PROJECT_ID"

BASE_DIR = os.path.dirname(__file__)
EXCEL_PATH = os.path.join(BASE_DIR, "streaming_cost_inflation.xlsx")


# --- Embedding & LLM Setup ---

embeddings_client = WatsonxEmbeddings(
    model_id="ibm/slate-30m-english-rtrvr-v2",
    url="https://us-south.ml.cloud.ibm.com",
    apikey=WATSONX_APIKEY,
    project_id=PROJECT_ID,
)

chat_params = TextChatParameters(
    max_completion_tokens=1024,
    temperature=0,
    seed=42,
)

watsonx_llm = ChatWatsonx(
    model_id="openai/gpt-oss-120b",
    url="https://us-south.ml.cloud.ibm.com",
    apikey=WATSONX_APIKEY,
    project_id=PROJECT_ID,
    params=chat_params,
)


# --- Helpers ---

def embed(texts: List[str]) -> np.ndarray:
    """Return numpy array of embeddings."""
    emb = embeddings_client.embed_documents(texts)
    return np.array(emb).astype("float32")


def load_excel_rows(path: str):
    df = pd.read_excel(path)
    docs = []
    for idx, row in df.iterrows():
        md = row.to_dict()
        text = "\n".join(f"{k}: {v}" for k, v in md.items())
        docs.append({"id": f"row-{idx}", "text": text, "metadata": md})
    return docs


def call_watsonx(prompt: str) -> str:
    return watsonx_llm.invoke(input=prompt).content


# --- FAISS Vector Store ---

class FAISSStore:
    def __init__(self):
        self.texts = []
        self.metadatas = []
        self.index = None
        self.dimension = None

    def add(self, docs: List[dict]):
        texts = [d["text"] for d in docs]
        metadata = [d["metadata"] for d in docs]

        emb = embed(texts)
        if self.index is None:
            self.dimension = emb.shape[1]
            self.index = faiss.IndexFlatIP(self.dimension)  # cosine via normalized vectors

        # normalize for cosine similarity
        faiss.normalize_L2(emb)

        self.index.add(emb)
        self.texts.extend(texts)
        self.metadatas.extend(metadata)

    def search(self, query: str, k: int = 5):
        q_emb = embed([query])
        faiss.normalize_L2(q_emb)

        distances, idxs = self.index.search(q_emb, k)

        results = []
        for score, idx in zip(distances[0], idxs[0]):
            if idx == -1:
                continue
            results.append({
                "text": self.texts[idx],
                "metadata": self.metadatas[idx],
                "score": float(score),
            })
        return results


# --- Main RAG ---

class ExcelRAG:
    def __init__(self):
        self.store = FAISSStore()

    def ingest(self, path: str):
        docs = load_excel_rows(path)
        self.store.add(docs)

    def ask(self, question: str, top_k: int):
        hits = self.store.search(question, k=top_k)
        if not hits:
            return "I couldn't find relevant info."

        context = "\n\n---\n\n".join(h["text"] for h in hits)
        prompt = (
            "You are a helpful assistant grounded in the following Excel data:\n\n"
            f"{context}\n\n"
            f"Question: {question}\n"
            "Answer:"
        )
        return call_watsonx(prompt)


# --- Orchestrate Tool ---

class RAGInput(BaseModel):
    question: str
    top_k: int = Field(5)


@tool(
    name="oic_excel_rag_tool",
    description="RAG search over Excel using Watsonx embeddings + FAISS",
    permission=ToolPermission.ADMIN
)
def excel_rag_tool(input: RAGInput) -> str:
    rag = ExcelRAG()
    rag.ingest(EXCEL_PATH)
    return rag.ask(input.question, input.top_k)
