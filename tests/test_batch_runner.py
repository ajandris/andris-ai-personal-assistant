"""Тесты пакетного прогона вопросов без обращения к OpenAI."""

import json

from openpyxl import Workbook, load_workbook

from app.rag.assistant_core import STAGE3_CONFIG, AssistantConfig
from app.rag.batch_runner import (
    DEFAULT_QUESTIONS_PATH,
    Variant,
    default_variants,
    index_dir_for,
    load_questions,
    run_batch,
    run_meta,
    select_questions,
    with_config_overrides,
    write_results,
)
from tests.test_assistant_core import FakeClient, make_record, write_jsonl


def make_questions_file(path, header_row=1):
    workbook = Workbook()
    sheet = workbook.active
    for _ in range(header_row - 1):
        sheet.append(["Заголовок листа"])
    sheet.append(["№", "Тип вопроса", "Вопрос (копировать в ноутбук)", "Ожидаемые факты", "Правильное поведение"])
    sheet.append([1, "Простой факт", "Какое образование у Андриса?", "Open University", "Ответить"])
    sheet.append(["№", None, None, None, None])  # повторная строка заголовков
    sheet.append([None, None, None, None, None])
    sheet.append([2, "Вне базы", "Какая погода в Лондоне?", "", "Отказ"])
    workbook.save(path)
    return path


def make_variants(tmp_path):
    records = tmp_path / "kb" / "records.jsonl"
    records.parent.mkdir()
    write_jsonl(records, [make_record("edu", "Андрис Янчевскис окончил Open University, образование высшее.")])
    p2 = AssistantConfig(intent_prompt_version="v2", answer_prompt_version="v2", strip_owner_name=True)
    return [Variant("V1", records, True, AssistantConfig(strip_owner_name=False), "первый"),
            Variant("V2", records, True, p2, "второй")]


def replies_for_two_questions():
    """Ответы LLM на два вопроса: факт (два вызова) и off_topic (один вызов)."""
    return [
        json.dumps({"intent": "fact", "search_query": "образование", "language": "ru"}),
        json.dumps({"answer": "=Окончил Open University [1].", "sufficient_context": True, "used_sources": [1]}),
        json.dumps({"intent": "off_topic", "search_query": "", "language": "ru"}),
    ]


def test_load_questions_finds_header_and_skips_noise(tmp_path):
    questions = load_questions(make_questions_file(tmp_path / "q.xlsx", header_row=3))
    assert [q["no"] for q in questions] == [1, 2]
    assert questions[0]["question"] == "Какое образование у Андриса?"
    assert questions[0]["expected"] == "Open University"


def test_bundled_stage3_questions_file_has_15_questions():
    questions = load_questions(DEFAULT_QUESTIONS_PATH)
    assert len(questions) == 15
    assert all(q["question"] and q["expected"] for q in questions)


def test_select_questions_by_number_and_limit(tmp_path):
    questions = load_questions(make_questions_file(tmp_path / "q.xlsx"))
    assert [q["no"] for q in select_questions(questions, ["2"])] == [2]
    assert len(select_questions(questions, limit=1)) == 1


def test_default_variants_change_one_thing_at_a_time():
    variants = default_variants()
    assert variants["A_v1"].config == STAGE3_CONFIG
    assert variants["A_p2"].records_path == variants["A_v1"].records_path
    assert variants["A2_p2"].config == variants["A_p2"].config
    assert variants["A2_p2_noname"].config.strip_owner_name and not variants["A2_p2"].config.strip_owner_name
    assert all(v.records_path.exists() for v in variants.values())
    # База A v3 сравнивается с v2 при тех же промптах и настройках.
    assert variants["A3_p2_noname"].config == variants["A2_p2_noname"].config
    assert variants["A3_p2_noname"].records_path != variants["A2_p2_noname"].records_path
    # answer_v3 — единственное отличие от A3_p2_noname_kw.
    kw, a3 = variants["A3_p2_noname_kw"], variants["A3_a3_noname_kw"]
    assert a3.config.answer_prompt_version == "v3" and kw.config.answer_prompt_version == "v2"
    assert (a3.records_path, a3.keywords_path) == (kw.records_path, kw.keywords_path)
    from dataclasses import replace
    assert replace(a3.config, answer_prompt_version="v2") == kw.config
    # B сравниваются с лучшим A на тех же промптах и настройках, но без таблицы ключевых слов.
    for name in ("B1_a3_noname", "B2_a3_noname"):
        b = variants[name]
        assert replace(b.config, kb_term_override=True) == a3.config and b.keywords_path is None
    a4 = variants["A3_a4_noname_kw"]
    assert replace(a4.config, answer_prompt_version="v3") == a3.config and a4.keywords_path == a3.keywords_path
    for name in ("B1_a4_noname", "B2_a4_noname"):
        assert replace(variants[name].config, kb_term_override=True) == a4.config


def test_bundled_holdout_questions_file_loads():
    questions = load_questions(DEFAULT_QUESTIONS_PATH.parent / "questions_holdout.xlsx")
    assert len(questions) == 26 and all(q["question"] and q["expected"] for q in questions)


def test_index_dir_differs_by_name_stripping_and_content(tmp_path):
    v1, v2 = make_variants(tmp_path)
    assert index_dir_for(v1, tmp_path) != index_dir_for(v2, tmp_path)
    before = index_dir_for(v1, tmp_path)
    write_jsonl(v1.records_path, [make_record("edu", "Изменённая запись.")])
    assert index_dir_for(v1, tmp_path) != before


def test_run_batch_runs_every_question_for_every_variant(tmp_path):
    questions = load_questions(make_questions_file(tmp_path / "q.xlsx"))
    variants = make_variants(tmp_path)
    client = FakeClient(replies_for_two_questions() * 2)
    saved = []
    rows, stop = run_batch(questions, variants, client, tmp_path / "cache", on_row=lambda r: saved.append(len(r)))
    assert stop == ""
    assert saved == [1, 2, 3, 4]
    assert [(r["variant"], r["no"], r["status"]) for r in rows] == [
        ("V1", 1, "answered"), ("V1", 2, "off_topic"), ("V2", 1, "answered"), ("V2", 2, "off_topic")]
    assert rows[0]["cited"] == "[1] Запись (edu)"
    assert rows[0]["fragments"].startswith("[1] ✓")
    assert rows[2]["embedded_query"] == "образование"
    assert len(client.chat_calls) == 6


def test_run_batch_reuses_cached_index(tmp_path):
    questions = select_questions(load_questions(make_questions_file(tmp_path / "q.xlsx")), ["2"])
    variant = make_variants(tmp_path)[:1]
    off_topic = json.dumps({"intent": "off_topic", "search_query": "", "language": "ru"})
    first = FakeClient([off_topic])
    run_batch(questions, variant, first, tmp_path / "cache")
    second = FakeClient([off_topic])
    run_batch(questions, variant, second, tmp_path / "cache")
    assert first.embedding_calls and not second.embedding_calls


def test_run_batch_records_provider_errors_and_stops(tmp_path):
    questions = load_questions(make_questions_file(tmp_path / "q.xlsx"))
    variants = make_variants(tmp_path)
    rows, stop = run_batch(questions, variants, FakeClient(fail_chat=True), tmp_path / "cache",
                           repeats=2, max_consecutive_errors=3)
    assert len(rows) == 3
    assert all(r["status"] == "error" and "insufficient_quota" in r["error"] for r in rows)
    assert "3 ошибок подряд" in stop


def test_write_results_creates_sheets_formulas_and_text_cells(tmp_path):
    questions = load_questions(make_questions_file(tmp_path / "q.xlsx"))
    variants = make_variants(tmp_path)
    rows, _ = run_batch(questions, variants, FakeClient(replies_for_two_questions() * 2), tmp_path / "cache")
    path = write_results(rows, variants, tmp_path / "out" / "result.xlsx", run_meta(tmp_path / "q.xlsx", questions, 1))
    workbook = load_workbook(path)
    assert workbook.sheetnames == ["Результаты", "Сводка", "Настройки", "Критерии"]
    results = workbook["Результаты"]
    headers = [c.value for c in results[1]]
    answer = results.cell(row=2, column=headers.index("Ответ") + 1)
    assert answer.value == "=Окончил Open University [1]." and answer.data_type == "s"
    assert results.max_row == 5
    summary = workbook["Сводка"]
    assert summary["A2"].value == "V1"
    assert summary["E2"].value.startswith("=IFERROR(ROUND(AVERAGEIFS(")
    settings = workbook["Настройки"]
    assert settings["A3"].value == "V2"


def test_config_overrides_change_chunking_and_index_dir(tmp_path):
    variants = make_variants(tmp_path)
    changed = with_config_overrides(variants, chunk_overlap=100)
    assert [v.config.chunk_overlap for v in changed] == [100, 100]
    assert [v.name for v in changed] == ["V1", "V2"]
    assert changed[1].config.strip_owner_name  # остальные настройки не меняются
    assert index_dir_for(changed[0], tmp_path) != index_dir_for(variants[0], tmp_path)
    assert with_config_overrides(variants) == variants


def test_config_overrides_reject_unknown_field(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        with_config_overrides(make_variants(tmp_path), overlap=0)


def test_cli_overrides_reach_every_variant(monkeypatch, tmp_path):
    import scripts.run_questions as cli
    args = cli.parse_args(["--answer-temperature", "0", "--chunk-overlap", "0", "--output", str(tmp_path / "r.xlsx")])
    assert args.answer_temperature == 0.0 and args.chunk_overlap == 0 and args.intent_temperature is None
    changed = with_config_overrides(make_variants(tmp_path), answer_temperature=args.answer_temperature)
    assert all(v.config.answer_temperature == 0.0 for v in changed)
