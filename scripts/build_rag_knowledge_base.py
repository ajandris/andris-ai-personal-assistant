"""Script to load knowledge base from external file in rag/knowledge_base,
generate OpenAI embeddings, and build the FAISS vector database in ./rag.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env
load_dotenv(ROOT_DIR / ".env")

from app.core.config import settings
from app.rag.vector_store import FAISSVectorStore
from openai import OpenAI

KNOWLEDGE_BASE_DIR = ROOT_DIR / "rag" / "knowledge_base"
DEFAULT_KNOWLEDGE_BASE_MD = KNOWLEDGE_BASE_DIR / "knowledge_base.md"
DEFAULT_KNOWLEDGE_BASE_JSON = KNOWLEDGE_BASE_DIR / "knowledge_base.json"


def parse_markdown_knowledge_base(content: str) -> List[Dict[str, Any]]:
    """Parse Markdown text into a list of knowledge document dictionaries."""
    sections = re.split(r"\n(?=##\s+)", content)
    documents: List[Dict[str, Any]] = []

    for section in sections:
        sec = section.strip()
        if not sec.startswith("## "):
            continue

        lines = sec.split("\n")
        title = lines[0].replace("## ", "").strip()
        doc_id = ""
        category = "general"
        source = ""
        url = ""
        tags: List[str] = []
        body_lines: List[str] = []

        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                continue

            if stripped.startswith("- **ID**:"):
                doc_id = re.sub(r"^- \*\*ID\*\*:\s*", "", stripped).strip().strip("`")
            elif re.match(r"^- \*\*(?:Категория|Category)\*\*:\s*", stripped, re.IGNORECASE):
                category = re.sub(r"^- \*\*(?:Категория|Category)\*\*:\s*", "", stripped, flags=re.IGNORECASE).strip()
            elif re.match(r"^- \*\*(?:Источник|Source)\*\*:\s*", stripped, re.IGNORECASE):
                source = re.sub(r"^- \*\*(?:Источник|Source)\*\*:\s*", "", stripped, flags=re.IGNORECASE).strip()
            elif stripped.startswith("- **URL**:"):
                url = re.sub(r"^- \*\*URL\*\*:\s*", "", stripped).strip()
            elif re.match(r"^- \*\*(?:Теги|Tags)\*\*:\s*", stripped, re.IGNORECASE):
                raw_tags = re.sub(r"^- \*\*(?:Теги|Tags)\*\*:\s*", "", stripped, flags=re.IGNORECASE).strip()
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            else:
                body_lines.append(line)

        body_text = "\n".join(body_lines).strip()

        if not doc_id:
            slug = re.sub(r"[^\w\s-]", "", title.lower())
            doc_id = re.sub(r"[-\s]+", "_", slug).strip("_") or f"doc_{len(documents) + 1}"

        documents.append({
            "id": doc_id,
            "category": category,
            "source": source,
            "url": url,
            "title": title,
            "tags": tags,
            "text": body_text,
        })

    return documents


def load_knowledge_base(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load knowledge documents from Markdown or JSON file."""
    target_path = path or (
        DEFAULT_KNOWLEDGE_BASE_MD
        if DEFAULT_KNOWLEDGE_BASE_MD.exists()
        else DEFAULT_KNOWLEDGE_BASE_JSON
    )
    if not target_path.exists():
        fallback_json = KNOWLEDGE_BASE_DIR / "documents.json"
        if fallback_json.exists():
            target_path = fallback_json
        else:
            raise FileNotFoundError(f"Knowledge base file not found at: {target_path}")

    if target_path.suffix.lower() == ".md":
        return parse_markdown_knowledge_base(target_path.read_text(encoding="utf-8"))

    with open(target_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_raw_knowledge_documents(source_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Assemble verified knowledge documents from external Markdown knowledge base file."""
    return load_knowledge_base(source_path)


def generate_embeddings_and_build_index(source_path: Optional[Path] = None):
    """Generate OpenAI embeddings for all knowledge chunks and save to FAISS store."""
    src = source_path or (
        DEFAULT_KNOWLEDGE_BASE_MD
        if DEFAULT_KNOWLEDGE_BASE_MD.exists()
        else DEFAULT_KNOWLEDGE_BASE_JSON
    )
    print("1. Assembling knowledge documents from Markdown knowledge base...")
    docs = get_raw_knowledge_documents(src)
    print(f"Total knowledge documents: {len(docs)} (loaded from {src})")

    # Ensure rag directory exists
    rag_dir = ROOT_DIR / "rag"
    rag_dir.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)

    # Generate embeddings with OpenAI
    api_key = settings.openai_api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured in .env or environment")

    client = OpenAI(api_key=api_key)
    embedding_model = settings.effective_embedding_model
    print(f"2. Generating embeddings using OpenAI model: {embedding_model}...")

    texts_to_embed = [
        f"{doc['title']}\nКатегория: {doc['category']}\nТеги: {', '.join(doc['tags'])}\n{doc['text']}"
        for doc in docs
    ]

    response = client.embeddings.create(
        input=texts_to_embed,
        model=embedding_model,
    )

    embeddings = [item.embedding for item in response.data]
    dim = len(embeddings[0])
    print(f"Generated {len(embeddings)} vectors with dimension {dim}")

    # Build FAISS store
    print(f"3. Building FAISS index (dimension={dim}, metric=cosine)...")
    store = FAISSVectorStore(dimension=dim, metric="cosine")
    store.add(vectors=embeddings, documents=docs)

    # Save to rag directory
    print(f"4. Saving FAISS index to {rag_dir}...")
    store.save(rag_dir)
    print(f"Successfully saved FAISS index with {store.count()} chunks in {rag_dir}")

    # Run verification test search
    print("5. Running sanity test search...")
    test_queries = [
        "Нужен разработчик на Python и FastAPI для создания RAG AI ассистента",
        "Ищем аналитика баз данных со знанием PostgreSQL и SQL",
        "Есть ли опыт в электронной коммерции на Django?",
        "Какое образование и дипломы у Андриса?",
    ]
    for q in test_queries:
        q_emb = client.embeddings.create(input=q, model=embedding_model).data[0].embedding
        hits = store.search(q_emb, top_k=2)
        try:
            print(f"\nQuery: '{q}'")
            for i, hit in enumerate(hits, 1):
                print(f"  [{i}] (Score: {hit['score']:.4f}) {hit['title']} ({hit['source']})")
        except UnicodeEncodeError:
            print(f"\nQuery: [unicode query]")
            for i, hit in enumerate(hits, 1):
                print(f"  [{i}] (Score: {hit['score']:.4f}) {hit['id']}")

    print("\nKnowledge base build completed successfully!")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    generate_embeddings_and_build_index()
