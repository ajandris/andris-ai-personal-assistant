"""Ядро AI-ассистента: RAG-поиск и два последовательных обращения к LLM.

Схема работы (один вопрос посетителя):

    вопрос
      │
      ▼
    [LLM-вызов 1] detect_intent ──► намерение + поисковый запрос
      │                              (off_topic → вежливый отказ без поиска)
      ▼
    [RAG] embed_texts + search ──► top_k фрагментов базы знаний
      │                              (нет фрагментов выше порога → отказ)
      ▼
    [LLM-вызов 2] generate_answer ─► ответ только по найденным фрагментам,
                                     номера источников, признак достаточности

Правила, по которым написан модуль (требования этапа 4 к ноутбуку):
- каждая функция использует только переданные ей параметры, глобальных переменных нет;
- клиент OpenAI передаётся параметром, поэтому функции можно тестировать с подставным
  клиентом и без API-ключа;
- все пути к файлам — параметры со значениями по умолчанию;
- модуль не импортирует ничего из приложения FastAPI, поэтому его функции можно
  перенести в ячейки ноутбука без изменений.

Модуль не подставляет готовых ответов: если LLM недоступна, вызывается исключение
AssistantError, и интерфейс должен честно сообщить об ошибке.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import faiss
import numpy as np
from pydantic import BaseModel, Field, ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORDS_PATH = PROJECT_ROOT / "knowledge_base" / "rag_a" / "records.jsonl"
DEFAULT_PROMPTS_DIR = PROJECT_ROOT / "prompts"
DEFAULT_INDEX_DIR = PROJECT_ROOT / "rag" / "index_rag_a"


# ---------------------------------------------------------------------------
# Настройки и структуры данных
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AssistantConfig:
    """Все параметры, которые меняются в экспериментах, собраны в одном месте."""

    language: str = "ru"                  # язык промптов и служебных сообщений
    site: str = "ru"                      # версия сайта: фильтр поля site у записей
    chunk_size: int = 800                 # максимальная длина фрагмента, символов
    chunk_overlap: int = 100              # перекрытие соседних фрагментов, символов
    top_k: int = 5                        # сколько фрагментов передавать во второй вызов
    min_score: float = 0.25               # порог косинусного сходства для фрагмента
    embedding_model: str = "text-embedding-3-small"
    llm_model: str = "gpt-4o-mini"
    intent_temperature: float = 0.0
    answer_temperature: float = 0.2
    intent_prompt_version: str = "v1"
    answer_prompt_version: str = "v1"


class IntentResult(BaseModel):
    """Результат первого вызова LLM."""

    intent: Literal["fact", "project", "job_match", "work_terms", "contact", "off_topic"]
    search_query: str = ""
    language: str = "ru"


class AnswerResult(BaseModel):
    """Результат второго вызова LLM."""

    answer: str = Field(min_length=1)
    sufficient_context: bool
    used_sources: list[int] = []


@dataclass
class AssistantResponse:
    """То, что получает интерфейс (ноутбук или сайт)."""

    answer: str
    status: Literal["answered", "insufficient_context", "no_context", "off_topic", "contact"]
    sources: list[dict[str, Any]] = field(default_factory=list)
    log: dict[str, Any] = field(default_factory=dict)


class AssistantError(Exception):
    """Ошибка провайдера LLM или невалидный ответ модели."""


# ---------------------------------------------------------------------------
# 1. База знаний
# ---------------------------------------------------------------------------

def load_records(path: str | Path = DEFAULT_RECORDS_PATH, site: str = "ru") -> list[dict[str, Any]]:
    """Читает records.jsonl и оставляет записи, допущенные к индексации.

    Допускаются записи с verified=true и public=true, у которых поле site равно
    "all" или коду нужной версии сайта.
    """
    records = []
    with open(path, encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue
            record = json.loads(line)
            if not (record.get("verified") and record.get("public")):
                continue
            if record.get("site", "all") not in ("all", site):
                continue
            records.append(record)
    return records


def split_text(text: str, chunk_size: int = 800, chunk_overlap: int = 100) -> list[str]:
    """Делит текст на фрагменты не длиннее chunk_size символов.

    Граница фрагмента по возможности ставится в конце предложения; следующий
    фрагмент начинается на chunk_overlap символов раньше конца предыдущего.
    """
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap должен быть меньше chunk_size")
    text = " ".join(text.split())
    if len(text) <= chunk_size:
        return [text] if text else []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            sentence_end = max(text.rfind(". ", start, end), text.rfind("! ", start, end), text.rfind("? ", start, end))
            if sentence_end > start + chunk_size // 2:
                end = sentence_end + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = max(end - chunk_overlap, start + 1)
    return chunks


def chunk_records(records: list[dict[str, Any]], chunk_size: int = 800, chunk_overlap: int = 100) -> list[dict[str, Any]]:
    """Превращает записи базы в фрагменты для индексации.

    Заголовок записи добавляется в начало каждого фрагмента, чтобы короткий
    фрагмент сохранял смысл. Метаданные источника сохраняются в каждом фрагменте.
    """
    chunks = []
    for record in records:
        parts = split_text(record["content"], chunk_size, chunk_overlap)
        for number, part in enumerate(parts, start=1):
            chunks.append({
                "chunk_id": f"{record['record_id']}#{number}",
                "record_id": record["record_id"],
                "entity_type": record.get("entity_type", ""),
                "title": record.get("title", ""),
                "source_url": record.get("source_url", ""),
                "text": f"{record.get('title', '')}. {part}",
            })
    return chunks


# ---------------------------------------------------------------------------
# 2. Эмбеддинги и векторный индекс FAISS
# ---------------------------------------------------------------------------

def embed_texts(texts: list[str], client: Any, model: str = "text-embedding-3-small", batch_size: int = 100) -> np.ndarray:
    """Получает эмбеддинги текстов от провайдера пакетами по batch_size."""
    vectors = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        try:
            response = client.embeddings.create(input=batch, model=model)
        except Exception as exc:  # ошибка сети, ключа, баланса и т. п.
            raise AssistantError(f"Ошибка при получении эмбеддингов: {exc}") from exc
        vectors.extend(item.embedding for item in response.data)
    return np.asarray(vectors, dtype=np.float32)


def normalize(vectors: np.ndarray) -> np.ndarray:
    """L2-нормализация: после неё скалярное произведение равно косинусному сходству."""
    vectors = np.asarray(vectors, dtype=np.float32)
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def build_index(vectors: np.ndarray) -> faiss.Index:
    """Создаёт индекс FAISS IndexFlatIP (точный поиск по косинусному сходству)."""
    vectors = normalize(vectors)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return index


def search(query_vector: np.ndarray, index: faiss.Index, chunks: list[dict[str, Any]],
           top_k: int = 5, min_score: float = 0.25) -> list[dict[str, Any]]:
    """Возвращает до top_k фрагментов с косинусным сходством не ниже min_score."""
    if index.ntotal == 0:
        return []
    scores, ids = index.search(normalize(query_vector), min(top_k, index.ntotal))
    hits = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0 or float(score) < min_score:
            continue
        hit = dict(chunks[idx])
        hit["score"] = round(float(score), 4)
        hits.append(hit)
    return hits


def save_index(index: faiss.Index, chunks: list[dict[str, Any]], config: AssistantConfig,
               directory: str | Path = DEFAULT_INDEX_DIR) -> Path:
    """Сохраняет индекс, фрагменты и параметры, с которыми индекс построен."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(directory / "index.faiss"))
    with open(directory / "chunks.json", "w", encoding="utf-8") as file:
        json.dump({"config": asdict(config), "chunks": chunks}, file, ensure_ascii=False, indent=2)
    return directory


def load_index(directory: str | Path = DEFAULT_INDEX_DIR) -> tuple[faiss.Index, list[dict[str, Any]], dict[str, Any]]:
    """Загружает индекс, фрагменты и параметры построения."""
    directory = Path(directory)
    index = faiss.read_index(str(directory / "index.faiss"))
    with open(directory / "chunks.json", encoding="utf-8") as file:
        data = json.load(file)
    return index, data["chunks"], data["config"]


def build_knowledge_index(client: Any, config: AssistantConfig,
                          records_path: str | Path = DEFAULT_RECORDS_PATH) -> tuple[faiss.Index, list[dict[str, Any]]]:
    """Полный цикл индексации: загрузка записей → фрагменты → эмбеддинги → индекс."""
    records = load_records(records_path, site=config.site)
    chunks = chunk_records(records, config.chunk_size, config.chunk_overlap)
    vectors = embed_texts([chunk["text"] for chunk in chunks], client, config.embedding_model)
    return build_index(vectors), chunks


# ---------------------------------------------------------------------------
# 3. Промпты и два обращения к LLM
# ---------------------------------------------------------------------------

def load_prompts(config: AssistantConfig, prompts_dir: str | Path = DEFAULT_PROMPTS_DIR) -> dict[str, Any]:
    """Читает версии промптов и служебные сообщения для языка из config."""
    folder = Path(prompts_dir) / config.language
    with open(folder / "messages.json", encoding="utf-8") as file:
        messages = json.load(file)
    return {
        "intent": (folder / f"intent_{config.intent_prompt_version}.txt").read_text(encoding="utf-8"),
        "answer": (folder / f"answer_{config.answer_prompt_version}.txt").read_text(encoding="utf-8"),
        "messages": messages,
    }


def call_llm_json(client: Any, model: str, system_prompt: str, user_content: str, temperature: float) -> dict[str, Any]:
    """Один вызов chat completions с ответом в формате JSON."""
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        raw = completion.choices[0].message.content or ""
    except Exception as exc:
        raise AssistantError(f"Ошибка обращения к LLM: {exc}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AssistantError(f"LLM вернула невалидный JSON: {raw[:200]}") from exc


def detect_intent(question: str, client: Any, model: str, prompt: str, temperature: float = 0.0) -> IntentResult:
    """LLM-вызов 1: определяет намерение и формирует поисковый запрос."""
    data = call_llm_json(client, model, prompt, f"Вопрос посетителя:\n{question}", temperature)
    try:
        return IntentResult.model_validate(data)
    except ValidationError as exc:
        raise AssistantError(f"Ответ первого шага не соответствует схеме: {data}") from exc


def format_context(hits: list[dict[str, Any]]) -> str:
    """Нумерует найденные фрагменты для второго промпта: [1] ..., [2] ..."""
    return "\n\n".join(f"[{number}] {hit['text']}" for number, hit in enumerate(hits, start=1))


def generate_answer(question: str, hits: list[dict[str, Any]], client: Any, model: str,
                    prompt: str, temperature: float = 0.2) -> AnswerResult:
    """LLM-вызов 2: формирует ответ строго по найденным фрагментам."""
    user_content = f"Контекст:\n{format_context(hits)}\n\nВопрос посетителя:\n{question}"
    data = call_llm_json(client, model, prompt, user_content, temperature)
    try:
        result = AnswerResult.model_validate(data)
    except ValidationError as exc:
        raise AssistantError(f"Ответ второго шага не соответствует схеме: {data}") from exc
    # Оставляем только номера, которые действительно есть в контексте.
    result.used_sources = sorted({n for n in result.used_sources if 1 <= n <= len(hits)})
    return result


# ---------------------------------------------------------------------------
# 4. Главная функция
# ---------------------------------------------------------------------------

def run_assistant(question: str, client: Any, index: faiss.Index, chunks: list[dict[str, Any]],
                  config: AssistantConfig, prompts: dict[str, Any]) -> AssistantResponse:
    """Обрабатывает один вопрос: намерение → поиск → ответ. Возвращает ответ и журнал шагов."""
    started = time.perf_counter()
    question = question.strip()
    log: dict[str, Any] = {"question": question, "config": asdict(config)}
    messages = prompts["messages"]

    intent = detect_intent(question, client, config.llm_model, prompts["intent"], config.intent_temperature)
    log["intent"] = intent.model_dump()

    if intent.intent == "off_topic":
        return AssistantResponse(messages["off_topic"], "off_topic", log=_finish(log, started))
    if intent.intent == "contact" and not intent.search_query.strip():
        return AssistantResponse(messages["contact"], "contact", log=_finish(log, started))

    query = intent.search_query.strip() or question
    query_vector = embed_texts([query], client, config.embedding_model)
    hits = search(query_vector, index, chunks, config.top_k, config.min_score)
    log["hits"] = [{"chunk_id": h["chunk_id"], "score": h["score"]} for h in hits]

    if not hits:
        return AssistantResponse(messages["no_context"], "no_context", log=_finish(log, started))

    result = generate_answer(question, hits, client, config.llm_model, prompts["answer"], config.answer_temperature)
    log["answer"] = result.model_dump()

    sources = [
        {"title": hits[n - 1]["title"], "source_url": hits[n - 1]["source_url"], "record_id": hits[n - 1]["record_id"]}
        for n in result.used_sources
    ]
    status = "answered" if result.sufficient_context else "insufficient_context"
    return AssistantResponse(result.answer, status, sources, log=_finish(log, started))


def _finish(log: dict[str, Any], started: float) -> dict[str, Any]:
    """Возвращает копию журнала с длительностью обработки вопроса."""
    return {**log, "duration_sec": round(time.perf_counter() - started, 3)}
