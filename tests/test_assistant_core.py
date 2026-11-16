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
    DEFAULT_KEYWORDS_PATH,
    DEFAULT_RECORDS_PATH,
    STAGE3_CONFIG,
    AssistantConfig,
    AssistantError,
    build_index,
    chunk_records,
    detect_intent,
    embedding_text,
    find_kb_term,
    load_keywords,
    load_or_build_index,
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
    # Формат работы с пунктом о переезде в Россию — только на русском сайте.
    assert "faq_work_format_ru_001" in ru_ids and "faq_work_format_ru_001" not in en_ids
    assert "faq_work_format_001" in en_ids and "faq_work_format_001" not in ru_ids


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

def test_default_config_is_the_best_stage4_variant_and_stage3_is_kept():
    best = AssistantConfig()
    assert (best.intent_prompt_version, best.answer_prompt_version) == ("v2", "v4")
    assert best.strip_owner_name and best.kb_term_override
    assert (best.chunk_overlap, best.intent_temperature, best.answer_temperature) == (0, 0.0, 0.0)
    assert DEFAULT_RECORDS_PATH.parent.name == "rag_a_v3" and DEFAULT_KEYWORDS_PATH.exists()
    assert (STAGE3_CONFIG.intent_prompt_version, STAGE3_CONFIG.answer_prompt_version) == ("v1", "v1")
    assert (STAGE3_CONFIG.chunk_overlap, STAGE3_CONFIG.answer_temperature) == (100, 0.2)
    assert not STAGE3_CONFIG.strip_owner_name and not STAGE3_CONFIG.kb_term_override


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


def test_run_assistant_source_number_matches_citation_in_answer(knowledge):
    index, chunks = knowledge
    client = FakeClient([
        '{"intent": "fact", "search_query": "Oracle TietoEnator", "language": "ru"}',
        '{"answer": "Ответ по второму фрагменту [2].", "sufficient_context": true, "used_sources": [2]}',
    ])
    config = AssistantConfig(min_score=0.0)
    response = run_assistant("Вопрос", client, index, chunks, config, load_prompts(config))
    assert [s["number"] for s in response.sources] == [2]


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
    assert response.sources[0]["number"] == 1
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


# --- версия v2: имя владельца, промпты v2, база A v2 -------------------------

RAG_A_V2_PATH = DEFAULT_RECORDS_PATH.parents[1] / "rag_a_v2" / "records.jsonl"


def test_embedding_text_keeps_text_when_stripping_is_off():
    text = "Андрис Янчевскис владеет латышским языком."
    assert embedding_text(text, AssistantConfig(strip_owner_name=False)) == text


def test_embedding_text_removes_owner_name_forms():
    config = AssistantConfig(strip_owner_name=True)
    assert embedding_text("Владение языками. Андрис Янчевскис владеет латышским.", config) == \
        "Владение языками. владеет латышским."
    assert embedding_text("Публичный профиль Андриса Янчевскиса на GitHub.", config) == "Публичный профиль на GitHub."
    assert embedding_text("Какое образование у Андриса?", config) == "Какое образование у?"
    assert embedding_text("Andris Jancevskis CV", config) == "CV"


def test_embedding_text_returns_original_if_only_name_left():
    assert embedding_text("Андрис", AssistantConfig(strip_owner_name=True)) == "Андрис"


def test_run_assistant_strips_name_only_from_embedded_query():
    config = AssistantConfig(strip_owner_name=True)
    chunks = chunk_records([make_record("edu", "Андрис Янчевскис окончил Open University, образование высшее.")])
    index = build_index(np.asarray([fake_embedding(embedding_text(c["text"], config)) for c in chunks], dtype=np.float32))
    client = FakeClient([
        json.dumps({"intent": "fact", "search_query": "образование Андриса Янчевскиса", "language": "ru"}),
        json.dumps({"answer": "Ответ [1].", "sufficient_context": True, "used_sources": [1]}),
    ])
    response = run_assistant("Какое образование у Андриса?", client, index, chunks, config, load_prompts(config))
    assert client.embedding_calls[-1] == ["образование"]
    assert response.log["embedded_query"] == "образование"
    assert response.status == "answered"
    # Второй вызов LLM получает исходный вопрос и исходный текст фрагмента с именем.
    second_call = client.chat_calls[1][1]["content"]
    assert "Какое образование у Андриса?" in second_call
    assert "Андрис Янчевскис окончил" in second_call


def test_v2_prompts_load_and_do_not_leak_profile_facts():
    config = AssistantConfig(intent_prompt_version="v2", answer_prompt_version="v2")
    prompts = load_prompts(config)
    for name in ("intent", "answer"):
        assert "JSON" in prompts[name]
        assert "стажир" not in prompts[name].lower()
    assert "гипотез" in prompts["answer"]
    assert "зарплат" in prompts["intent"]


def test_rag_a_v2_splits_languages_and_formats():
    records = {r["record_id"]: r for r in load_records(RAG_A_V2_PATH, site="ru")}
    assert "skill_languages_001" not in records
    languages = records["skill_programming_languages_001"]
    assert "JSON" not in languages["skills"] and "REST API" not in languages["skills"]
    assert records["skill_data_formats_001"]["skills"] == ["JSON", "REST API"]
    assert "skill_programming_levels_001" in records



def test_rag_a_v3_fixes_current_job_education_and_languages():
    records = {r["record_id"]: r for r in load_records(RAG_A_V2_PATH.parents[1] / "rag_a_v3" / "records.jsonl", site="ru")}
    assert records["experience_boots_001"]["title"].startswith("Текущее место работы")
    assert "Wrexham" in records["education_higher_001"]["content"] and "Open University" in records["education_higher_001"]["content"]
    # Уровни опыта — отдельная запись: объединённая запись не помещалась в один фрагмент (800 символов).
    levels = records["skill_programming_levels_001"]["content"]
    assert "Django" in levels and "1 года учебного опыта в Code Institute" in levels
    assert "уровень опыта" in records["skill_programming_languages_001"]["content"]
    assert all(len(r["content"]) <= 800 for r in records.values())


def test_load_keywords_and_find_kb_term(tmp_path):
    path = tmp_path / "keywords.csv"
    path.write_text("keyword,category,comment\ncandlemania,project,блог\nПетробалт,fact,стажировка\n# черновик,,\n,,\n",
                    encoding="utf-8-sig")
    keywords = load_keywords(path)
    assert keywords == {"candlemania": "project", "Петробалт": "fact"}
    assert find_kb_term("Правда ли, что Candlemania — интернет-магазин?", keywords) == "candlemania"
    assert find_kb_term("Что он делал в Петробалте?", keywords) == "Петробалт"
    assert find_kb_term("Какая погода в Лондоне?", keywords) == ""


def test_load_keywords_rejects_unknown_or_off_topic_category(tmp_path):
    for category in ("off_topic", "", "проект"):
        path = tmp_path / "keywords.csv"
        path.write_text(f"keyword,category,comment\ncandlemania,{category},\n", encoding="utf-8")
        with pytest.raises(ValueError, match="строка 2"):
            load_keywords(path)


def test_bundled_keywords_table_loads():
    keywords = load_keywords(RAG_A_V2_PATH.parents[1] / "rag_a_v3" / "keywords.csv")
    assert keywords["candlemania"] == "project" and "postgres_db_desc" in keywords


def test_run_assistant_overrides_off_topic_only_when_enabled():
    record = {**make_record("p", "candlemania это блог свечей а не интернет-магазин"), "entity_type": "project",
              "title": "candlemania: назначение"}
    chunks = chunk_records([record])
    index = build_index(np.asarray([fake_embedding(c["text"]) for c in chunks], dtype=np.float32))
    off_topic = json.dumps({"intent": "off_topic", "search_query": "", "language": "ru"})
    answer = json.dumps({"answer": "Нет, это блог [1].", "sufficient_context": True, "used_sources": [1]})
    question = "Правда ли что candlemania это интернет-магазин свечей"
    keywords = {"candlemania": "project"}

    plain_config = AssistantConfig(kb_term_override=False)
    plain = run_assistant(question, FakeClient([off_topic]), index, chunks, plain_config,
                          load_prompts(plain_config), keywords)
    assert plain.status == "off_topic"

    config = AssistantConfig(kb_term_override=True)
    no_table = run_assistant(question, FakeClient([off_topic]), index, chunks, config, load_prompts(config))
    assert no_table.status == "off_topic"

    client = FakeClient([off_topic, answer])
    response = run_assistant(question, client, index, chunks, config, load_prompts(config), keywords)
    assert response.status == "answered"
    assert response.log["kb_term_override"] == {"keyword": "candlemania", "category": "project"}
    assert response.log["intent"]["intent"] == "off_topic"  # журнал хранит исходный ответ шага 1
    assert client.embedding_calls[-1] == [question]


def test_keyword_with_contact_category_gives_contact_message():
    chunks = chunk_records([make_record("c", "Форма на странице Контакты.")])
    index = build_index(np.asarray([fake_embedding(c["text"]) for c in chunks], dtype=np.float32))
    off_topic = json.dumps({"intent": "off_topic", "search_query": "", "language": "ru"})
    config = AssistantConfig(kb_term_override=True)
    response = run_assistant("Хочу написать в LinkedIn", FakeClient([off_topic]), index, chunks, config,
                             load_prompts(config), {"LinkedIn": "contact"})
    assert response.status == "contact"


def test_answer_v3_differs_from_v2_only_by_completeness_and_contact_rules():
    v2 = load_prompts(AssistantConfig(answer_prompt_version="v2"))["answer"]
    v3 = load_prompts(AssistantConfig(answer_prompt_version="v3"))["answer"]
    assert v3 != v2 and "стажир" not in v3.lower()
    assert "Не сокращай фрагмент" in v3 and "всегда предложи связаться" in v3


def test_load_or_build_index_reuses_index_until_base_changes(tmp_path):
    records = tmp_path / "records.jsonl"
    write_jsonl(records, [make_record("a", "Первая запись о Python.")])
    config = AssistantConfig()
    first = FakeClient()
    _, chunks = load_or_build_index(first, config, records, tmp_path / "index")
    assert first.embedding_calls and chunks[0]["record_id"] == "a"

    second = FakeClient()
    load_or_build_index(second, config, records, tmp_path / "index")
    assert not second.embedding_calls  # индекс загружен с диска

    write_jsonl(records, [make_record("b", "Изменённая запись о FastAPI.")])
    third = FakeClient()
    _, chunks = load_or_build_index(third, config, records, tmp_path / "index")
    assert third.embedding_calls and chunks[0]["record_id"] == "b"
