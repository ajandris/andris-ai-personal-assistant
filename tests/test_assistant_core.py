"""Тесты ядра AI-ассистента без обращения к OpenAI.

Вместо настоящего клиента используется FakeClient:
- эмбеддинги строятся детерминированно из слов текста (общие слова → близкие векторы);
- ответы чата берутся из заранее заданной очереди JSON-строк.

Тесты проверяют логику нашего кода (фильтрацию базы, чанкинг, поиск, порядок шагов,
обработку ошибок), а не качество ответов модели. Качество проверяется отдельно,
в экспериментах с настоящим API.
"""

import hashlib
import json
from types import SimpleNamespace

import numpy as np
import pytest

from app.rag.assistant_core import (
    DEFAULT_RECORDS_PATH,
    AssistantConfig,
    AssistantError,
    build_index,
    chunk_records,
    detect_intent,
    generate_answer,
    load_index,
    load_prompts,
    load_records,
    run_assistant,
    save_index,
    search,
    split_text,
)

DIM = 512


def fake_embedding(text: str) -> list[float]:
    """Мешок слов, захэшированный в вектор фиксированной длины."""
    vector = np.zeros(DIM, dtype=np.float32)
    for word in text.lower().replace(",", " ").replace(".", " ").split():
        if len(word) > 2:
            vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM] += 1.0
    return vector.tolist()


class FakeClient:
    """Подставной клиент с тем же интерфейсом, что у openai.OpenAI."""

    def __init__(self, chat_replies=None, fail_chat=False):
        self.chat_replies = list(chat_replies or [])
        self.chat_calls = []
        self.embedding_calls = []
        self.fail_chat = fail_chat
        self.embeddings = SimpleNamespace(create=self._embed)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._chat))

    def _embed(self, input, model):
        self.embedding_calls.append(list(input))
        return SimpleNamespace(data=[SimpleNamespace(embedding=fake_embedding(t)) for t in input])

    def _chat(self, model, messages, temperature, response_format):
        self.chat_calls.append(messages)
        if self.fail_chat:
            raise RuntimeError("insufficient_quota")
        content = self.chat_replies.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def write_jsonl(path, records):
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")


def make_record(record_id, content, verified=True, public=True, site=None, title="Запись"):
    record = {"record_id": record_id, "entity_type": "fact", "title": title, "content": content,
              "source_url": "src", "verified": verified, "public": public}
    if site:
        record["site"] = site
    return record


@pytest.fixture(scope="module")
def knowledge():
    """Индекс по настоящей базе RAG A, построенный на подставных эмбеддингах."""
    config = AssistantConfig()
    chunks = chunk_records(load_records(DEFAULT_RECORDS_PATH, site="ru"), config.chunk_size, config.chunk_overlap)
    vectors = np.asarray([fake_embedding(c["text"]) for c in chunks], dtype=np.float32)
    return build_index(vectors), chunks


# --- база знаний -----------------------------------------------------------

def test_load_records_filters_unverified_private_and_other_site(tmp_path):
    path = tmp_path / "records.jsonl"
    write_jsonl(path, [
        make_record("ok_001", "Подтверждённый факт."),
        make_record("unverified_001", "Непроверенный факт.", verified=False),
        make_record("private_001", "Закрытый факт.", public=False),
        make_record("ru_only_001", "Только для русского сайта.", site="ru"),
    ])
    assert [r["record_id"] for r in load_records(path, site="ru")] == ["ok_001", "ru_only_001"]
    assert [r["record_id"] for r in load_records(path, site="en")] == ["ok_001"]


def test_real_knowledge_base_respects_site_field():
    ru_ids = {r["record_id"] for r in load_records(DEFAULT_RECORDS_PATH, site="ru")}
    en_ids = {r["record_id"] for r in load_records(DEFAULT_RECORDS_PATH, site="en")}
    assert "faq_relocation_russia_001" in ru_ids
    assert "faq_relocation_russia_001" not in en_ids


def test_split_text_keeps_short_text_whole():
    assert split_text("Короткий текст.", 800, 100) == ["Короткий текст."]


def test_split_text_respects_size_and_overlap():
    text = " ".join(f"Предложение номер {i} о проекте." for i in range(60))
    chunks = split_text(text, chunk_size=200, chunk_overlap=40)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)
    # Начало второго фрагмента повторяет конец первого (перекрытие).
    assert chunks[1][:15] in chunks[0]


def test_split_text_rejects_overlap_not_smaller_than_size():
    with pytest.raises(ValueError):
        split_text("текст", chunk_size=100, chunk_overlap=100)


def test_chunk_records_keeps_metadata_and_title():
    chunks = chunk_records([make_record("rec_001", "Факт о проекте.", title="Проект")])
    assert chunks[0]["chunk_id"] == "rec_001#1"
    assert chunks[0]["record_id"] == "rec_001"
    assert chunks[0]["source_url"] == "src"
    assert chunks[0]["text"].startswith("Проект.")


# --- поиск ------------------------------------------------------------------

def test_search_finds_relevant_record(knowledge):
    index, chunks = knowledge
    query = np.asarray([fake_embedding("Oracle TietoEnator Financial Solutions")], dtype=np.float32)
    hits = search(query, index, chunks, top_k=3, min_score=0.0)
    assert hits[0]["record_id"].startswith("experience_latvia_tietoenator")
    assert hits[0]["score"] >= hits[-1]["score"]


def test_search_applies_min_score(knowledge):
    index, chunks = knowledge
    query = np.asarray([fake_embedding("квантовая астрофизика зебры")], dtype=np.float32)
    assert search(query, index, chunks, top_k=5, min_score=0.5) == []


def test_save_and_load_index_roundtrip(tmp_path, knowledge):
    index, chunks = knowledge
    save_index(index, chunks, AssistantConfig(), directory=tmp_path)
    loaded_index, loaded_chunks, saved_config = load_index(tmp_path)
    assert loaded_index.ntotal == index.ntotal
    assert loaded_chunks == chunks
    assert saved_config["chunk_size"] == 800


# --- промпты и вызовы LLM ---------------------------------------------------

def test_load_prompts_reads_russian_versions():
    prompts = load_prompts(AssistantConfig())
    assert "search_query" in prompts["intent"]
    assert "sufficient_context" in prompts["answer"]
    assert set(prompts["messages"]) == {"off_topic", "no_context", "contact"}


def test_detect_intent_rejects_invalid_json():
    client = FakeClient(["это не JSON"])
    with pytest.raises(AssistantError):
        detect_intent("Вопрос", client, "model", "prompt")


def test_detect_intent_rejects_unknown_intent():
    client = FakeClient(['{"intent": "weather", "search_query": "", "language": "ru"}'])
    with pytest.raises(AssistantError):
        detect_intent("Вопрос", client, "model", "prompt")


def test_generate_answer_drops_source_numbers_outside_context():
    hits = [{"text": "Факт 1"}, {"text": "Факт 2"}]
    client = FakeClient(['{"answer": "Ответ [1]", "sufficient_context": true, "used_sources": [1, 5, 1]}'])
    result = generate_answer("Вопрос", hits, client, "model", "prompt")
    assert result.used_sources == [1]


# --- главная функция --------------------------------------------------------

def test_run_assistant_makes_two_llm_calls_and_returns_sources(knowledge):
    index, chunks = knowledge
    client = FakeClient([
        '{"intent": "fact", "search_query": "Oracle TietoEnator", "language": "ru"}',
        '{"answer": "Андрис работал с Oracle в TietoEnator [1].", "sufficient_context": true, "used_sources": [1]}',
    ])
    config = AssistantConfig(min_score=0.0)
    response = run_assistant("С какими СУБД работал Андрис?", client, index, chunks, config, load_prompts(config))

    assert response.status == "answered"
    assert len(client.chat_calls) == 2
    second_call_user_message = client.chat_calls[1][1]["content"]
    assert "Контекст:" in second_call_user_message and "[1]" in second_call_user_message
    assert response.sources and response.sources[0]["record_id"].startswith("experience_latvia_tietoenator")
    assert response.log["intent"]["search_query"] == "Oracle TietoEnator"
    assert "duration_sec" in response.log


def test_run_assistant_off_topic_skips_search_and_second_call(knowledge):
    index, chunks = knowledge
    client = FakeClient(['{"intent": "off_topic", "search_query": "", "language": "ru"}'])
    config = AssistantConfig()
    response = run_assistant("Какая завтра погода?", client, index, chunks, config, load_prompts(config))
    assert response.status == "off_topic"
    assert len(client.chat_calls) == 1
    assert client.embedding_calls == []


def test_run_assistant_without_relevant_context_refuses(knowledge):
    index, chunks = knowledge
    client = FakeClient(['{"intent": "fact", "search_query": "квантовая астрофизика зебры", "language": "ru"}'])
    config = AssistantConfig(min_score=0.99)
    response = run_assistant("Есть ли опыт в астрофизике?", client, index, chunks, config, load_prompts(config))
    assert response.status == "no_context"
    assert len(client.chat_calls) == 1
    assert "нет сведений" in response.answer


def test_run_assistant_reports_insufficient_context(knowledge):
    index, chunks = knowledge
    client = FakeClient([
        '{"intent": "job_match", "search_query": "Kubernetes DevOps", "language": "ru"}',
        '{"answer": "Подтверждённого опыта с Kubernetes нет [1].", "sufficient_context": false, "used_sources": [1]}',
    ])
    config = AssistantConfig(min_score=0.0)
    response = run_assistant("Нужен DevOps с Kubernetes", client, index, chunks, config, load_prompts(config))
    assert response.status == "insufficient_context"


def test_run_assistant_raises_on_provider_error_instead_of_fake_answer(knowledge):
    index, chunks = knowledge
    client = FakeClient(fail_chat=True)
    config = AssistantConfig()
    with pytest.raises(AssistantError):
        run_assistant("Вопрос", client, index, chunks, config, load_prompts(config))
