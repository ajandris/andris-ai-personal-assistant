"""Tests for FAISS vector store and RAG directory configuration."""

from pathlib import Path
import numpy as np
import pytest

from app.core.config import get_settings
from app.rag import FAISSVectorStore


def test_vector_db_path_configured_to_rag():
    """Проверка, что vector_db_path в настройках указывает на ./rag."""
    settings = get_settings()
    assert settings.vector_db_path == "./rag"


def test_rag_directory_exists():
    """Проверка, что директория rag создана в корне проекта."""
    root_rag = Path(__file__).resolve().parent.parent / "rag"
    assert root_rag.exists()
    assert root_rag.is_dir()


def test_faiss_vector_store_add_and_search():
    """Проверка добавления эмбеддингов в FAISS и косинусного поиска."""
    dimension = 4
    store = FAISSVectorStore(dimension=dimension, metric="cosine")

    # Создаем 3 вектора
    v1 = [1.0, 0.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0, 0.0]
    v3 = [0.7071, 0.7071, 0.0, 0.0]

    docs = [
        {"title": "Doc A", "text": "Текст про AI"},
        {"title": "Doc B", "text": "Текст про базы данных"},
        {"title": "Doc C", "text": "Текст про AI и базы данных"},
    ]

    total = store.add([v1, v2, v3], docs)
    assert total == 3
    assert store.count() == 3

    # Ищем вектор, близкий к Doc A
    query = [1.0, 0.0, 0.0, 0.0]
    results = store.search(query, top_k=2)

    assert len(results) == 2
    assert results[0]["title"] == "Doc A"
    assert pytest.approx(results[0]["score"], 0.001) == 1.0
    assert results[1]["title"] == "Doc C"


def test_faiss_save_and_load(tmp_path: Path):
    """Проверка сохранения индекса FAISS и метаданных на диск и их загрузки."""
    dimension = 3
    store = FAISSVectorStore(dimension=dimension, metric="cosine")

    vectors = np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ], dtype=np.float32)

    docs = [
        {"id": 1, "text": "Первый чанк"},
        {"id": 2, "text": "Второй чанк"},
    ]

    store.add(vectors, docs)

    # Сохраняем во временную директорию
    saved_dir = store.save(tmp_path)
    assert (saved_dir / "index.faiss").exists()
    assert (saved_dir / "chunks.json").exists()

    # Загружаем из директории
    loaded_store = FAISSVectorStore.load(saved_dir)
    assert loaded_store.count() == 2
    assert loaded_store.dimension == dimension

    # Выполняем поиск в загруженном хранилище
    res = loaded_store.search([0.0, 1.0, 0.0], top_k=1)
    assert len(res) == 1
    assert res[0]["id"] == 2


def test_rag_knowledge_base_folder_and_file_exist():
    """Проверка, что папка rag/knowledge_base и файл базы знаний Markdown существуют."""
    from scripts.build_rag_knowledge_base import (
        DEFAULT_KNOWLEDGE_BASE_MD,
        KNOWLEDGE_BASE_DIR,
        load_knowledge_base,
    )

    assert KNOWLEDGE_BASE_DIR.exists()
    assert KNOWLEDGE_BASE_DIR.is_dir()
    assert DEFAULT_KNOWLEDGE_BASE_MD.exists()

    docs = load_knowledge_base()
    assert isinstance(docs, list)
    assert len(docs) >= 20

    first_doc = docs[0]
    for required_key in ["id", "category", "source", "url", "title", "tags", "text"]:
        assert required_key in first_doc


def test_markdown_knowledge_base_parser(tmp_path: Path):
    """Проверка парсинга базы знаний в формате Markdown."""
    from scripts.build_rag_knowledge_base import (
        load_knowledge_base,
        parse_markdown_knowledge_base,
    )

    sample_md = """# Заголовок документа

## Компетенции в AI и Python
- **ID**: ai_python_skills
- **Категория**: skills
- **Источник**: Site & CV
- **URL**: /skills
- **Теги**: ai, python, fastapi, rag

Андрис разрабатывает масштабируемые AI-решения на Python и FastAPI.
Реализована поддержка RAG и векторного поиска.
"""
    parsed = parse_markdown_knowledge_base(sample_md)
    assert len(parsed) == 1
    doc = parsed[0]
    assert doc["id"] == "ai_python_skills"
    assert doc["category"] == "skills"
    assert doc["source"] == "Site & CV"
    assert doc["url"] == "/skills"
    assert doc["title"] == "Компетенции в AI и Python"
    assert "fastapi" in doc["tags"]
    assert "Андрис разрабатывает масштабируемые AI-решения" in doc["text"]

    target_md = tmp_path / "custom_kb.md"
    target_md.write_text(sample_md, encoding="utf-8")
    reloaded = load_knowledge_base(target_md)
    assert len(reloaded) == 1
    assert reloaded[0]["id"] == "ai_python_skills"
    assert reloaded[0]["text"] == doc["text"]


def test_rag_knowledge_base_exempt_from_git():
    """Проверка, что rag/* исключает rag/knowledge_base/ из системы контроля версий Git."""
    gitignore_path = Path(__file__).resolve().parent.parent / ".gitignore"
    content = gitignore_path.read_text(encoding="utf-8")
    assert "rag/*" in content



