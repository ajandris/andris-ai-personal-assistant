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
