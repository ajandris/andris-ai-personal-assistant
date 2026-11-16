"""Пакетный прогон тестовых вопросов через ассистента с записью результатов в Excel.

Утилита задаёт каждый вопрос из списка каждому варианту ассистента (вариант =
база знаний + настройки AssistantConfig) и сохраняет ответы, статусы, найденные
фрагменты и журнал шагов в таблицу Excel. В таблице есть пустые столбцы для
ручной оценки (0–2, «выдумка») и лист «Сводка» с формулами, которые
пересчитываются после выставления оценок.

Правила те же, что у assistant_core: клиент OpenAI и пути передаются
параметрами, глобальных переменных функции не используют. Ошибка провайдера не
заменяется готовым ответом: она записывается в строку результата со статусом
"error", а после нескольких ошибок подряд прогон останавливается.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from app.rag.assistant_core import (
    DEFAULT_PROMPTS_DIR,
    PROJECT_ROOT,
    STAGE3_CONFIG,
    AssistantConfig,
    AssistantError,
    build_knowledge_index,
    load_index,
    load_keywords,
    load_prompts,
    run_assistant,
    save_index,
)

DEFAULT_QUESTIONS_PATH = PROJECT_ROOT / "experiments" / "questions_stage3.xlsx"
DEFAULT_CACHE_DIR = PROJECT_ROOT / "rag" / "index_cache"
KB_DIR = PROJECT_ROOT / "knowledge_base"

STATUSES = ["answered", "insufficient_context", "no_context", "off_topic", "contact", "error"]


# ---------------------------------------------------------------------------
# Варианты ассистента
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Variant:
    """Один вариант ассистента для сравнения: база знаний и настройки."""

    name: str
    records_path: Path
    require_verified: bool
    config: AssistantConfig = field(default_factory=AssistantConfig)
    description: str = ""
    keywords_path: Path | None = None     # таблица ключевых слов базы (для kb_term_override)


def default_variants(kb_dir: str | Path = KB_DIR) -> dict[str, Variant]:
    """Варианты для повторного прогона 15 вопросов этапа 3 (шаг 2 этапа 4).

    Соседние варианты одной базы отличаются одним изменением, поэтому вклад
    каждого изменения виден отдельно: промпты v2 → база A v2 → имя владельца
    убрано из текста для эмбеддингов → база A v3 (те же промпты и настройки).
    """
    kb_dir = Path(kb_dir)
    # Все варианты строятся от настроек этапа 3: значения AssistantConfig по
    # умолчанию теперь равны лучшему варианту, а сравнения должны оставаться
    # такими, какими они были в экспериментах (overlap и температуру меняют
    # параметры командной строки).
    v1 = STAGE3_CONFIG
    p2 = replace(v1, intent_prompt_version="v2", answer_prompt_version="v2")
    p2_noname = replace(p2, strip_owner_name=True)
    p2_noname_kw = replace(p2_noname, kb_term_override=True)
    a3_noname_kw = replace(p2_noname_kw, answer_prompt_version="v3")
    a3_noname = replace(p2_noname, answer_prompt_version="v3")
    a4_noname_kw = replace(p2_noname_kw, answer_prompt_version="v4")
    a4_noname = replace(p2_noname, answer_prompt_version="v4")
    a1, a2 = kb_dir / "rag_a" / "records.jsonl", kb_dir / "rag_a_v2" / "records.jsonl"
    a3 = kb_dir / "rag_a_v3" / "records.jsonl"
    b1, b2 = kb_dir / "rag_b" / "records.jsonl", kb_dir / "rag_b2" / "records.jsonl"
    variants = [
        Variant("A_v1", a1, True, v1, "База A v1, промпты v1 (настройки этапа 3)"),
        Variant("A_p2", a1, True, p2, "База A v1, промпты v2"),
        Variant("A2_p2", a2, True, p2, "База A v2, промпты v2"),
        Variant("A2_p2_noname", a2, True, p2_noname, "База A v2, промпты v2, без имени в эмбеддингах"),
        Variant("A3_p2", a3, True, p2, "База A v3, промпты v2"),
        Variant("A3_p2_noname", a3, True, p2_noname, "База A v3, промпты v2, без имени в эмбеддингах"),
        Variant("A3_p2_noname_kw", a3, True, p2_noname_kw,
                "База A v3, промпты v2, без имени в эмбеддингах, off_topic отменяется по таблице ключевых слов",
                keywords_path=kb_dir / "rag_a_v3" / "keywords.csv"),
        Variant("A3_a3_noname_kw", a3, True, a3_noname_kw,
                "База A v3, intent_v2 + answer_v3, без имени в эмбеддингах, таблица ключевых слов",
                keywords_path=kb_dir / "rag_a_v3" / "keywords.csv"),
        Variant("B1_v1", b1, False, v1, "База B1, промпты v1 (настройки этапа 3)"),
        Variant("B1_p2", b1, False, p2, "База B1, промпты v2"),
        Variant("B1_p2_noname", b1, False, p2_noname, "База B1, промпты v2, без имени в эмбеддингах"),
        Variant("B2_v1", b2, False, v1, "База B2, промпты v1 (настройки этапа 3)"),
        Variant("B2_p2", b2, False, p2, "База B2, промпты v2"),
        Variant("B2_p2_noname", b2, False, p2_noname, "База B2, промпты v2, без имени в эмбеддингах"),
        # Итоговое сравнение A и B на одинаковых промптах и настройках. У баз B нет
        # таблицы ключевых слов: её ведёт автор редактируемой базы, при парсинге сайта её нет.
        Variant("B1_a3_noname", b1, False, a3_noname, "База B1, intent_v2 + answer_v3, без имени в эмбеддингах"),
        Variant("B2_a3_noname", b2, False, a3_noname, "База B2, intent_v2 + answer_v3, без имени в эмбеддингах"),
        # Проверка на новых вопросах (experiments/questions_holdout.xlsx): answer_v4 = answer_v3 +
        # предложение прислать подробное описание вакансии.
        Variant("A3_a4_noname_kw", a3, True, a4_noname_kw,
                "База A v3, intent_v2 + answer_v4, без имени в эмбеддингах, таблица ключевых слов",
                keywords_path=kb_dir / "rag_a_v3" / "keywords.csv"),
        Variant("B1_a4_noname", b1, False, a4_noname, "База B1, intent_v2 + answer_v4, без имени в эмбеддингах"),
        Variant("B2_a4_noname", b2, False, a4_noname, "База B2, intent_v2 + answer_v4, без имени в эмбеддингах"),
    ]
    return {variant.name: variant for variant in variants}


def with_config_overrides(variants: list[Variant], **changes: Any) -> list[Variant]:
    """Копии вариантов, у которых изменены поля AssistantConfig (например, chunk_overlap=0).

    Имена и описания вариантов не меняются: изменённые значения видны на листе
    «Настройки», а индекс FAISS строится заново, потому что параметры
    чанкинга входят в имя папки кэша.
    """
    if not changes:
        return list(variants)
    unknown = set(changes) - set(asdict(AssistantConfig()))
    if unknown:
        raise ValueError(f"Неизвестные параметры AssistantConfig: {', '.join(sorted(unknown))}")
    return [replace(v, config=replace(v.config, **changes)) for v in variants]


# ---------------------------------------------------------------------------
# Вопросы
# ---------------------------------------------------------------------------

QUESTION_COLUMNS = {
    "№": "no",
    "Тип вопроса": "type",
    "Вопрос": "question",
    "Ожидаемые факты": "expected",
    "Правильное поведение": "behaviour",
}


def load_questions(path: str | Path = DEFAULT_QUESTIONS_PATH, sheet: str | None = None) -> list[dict[str, Any]]:
    """Читает вопросы из Excel.

    Строка заголовков ищется по ячейке, которая начинается со слова «Вопрос»;
    обязательны столбцы «№» и «Вопрос», остальные («Тип вопроса», «Ожидаемые
    факты», «Правильное поведение») необязательны. Пустые строки и повторные
    строки заголовков пропускаются.
    """
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook[sheet] if sheet else workbook.worksheets[0]
    rows = list(worksheet.iter_rows(values_only=True))
    workbook.close()

    header_index, columns = None, {}
    for number, row in enumerate(rows):
        for position, value in enumerate(row):
            title = str(value).strip() if value is not None else ""
            for prefix, key in QUESTION_COLUMNS.items():
                if title == prefix or (key == "question" and title.startswith("Вопрос (")):
                    columns.setdefault(key, position)
        if "question" in columns and "no" in columns:
            header_index = number
            break
        columns = {}
    if header_index is None:
        raise ValueError(f"В файле {path} не найдена строка заголовков со столбцами «№» и «Вопрос»")

    questions = []
    for row in rows[header_index + 1:]:
        cells = {key: row[position] if position < len(row) else None for key, position in columns.items()}
        text = str(cells.get("question") or "").strip()
        if not text or str(cells.get("no")).strip() == "№":
            continue
        questions.append({
            "no": cells.get("no"),
            "type": str(cells.get("type") or ""),
            "question": text,
            "expected": str(cells.get("expected") or ""),
            "behaviour": str(cells.get("behaviour") or ""),
        })
    return questions


def select_questions(questions: list[dict[str, Any]], numbers: list[str] | None = None,
                     limit: int | None = None) -> list[dict[str, Any]]:
    """Оставляет вопросы с указанными номерами и/или первые limit вопросов."""
    if numbers:
        wanted = {str(n).strip() for n in numbers}
        questions = [q for q in questions if str(q["no"]).strip() in wanted]
    return questions[:limit] if limit else questions


# ---------------------------------------------------------------------------
# Индексы и прогон
# ---------------------------------------------------------------------------

def file_fingerprint(path: str | Path) -> str:
    """Короткий хэш содержимого файла: после правки базы индекс строится заново."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def index_dir_for(variant: Variant, cache_dir: str | Path = DEFAULT_CACHE_DIR) -> Path:
    """Папка индекса: своя для базы (по содержимому), модели эмбеддингов, чанкинга и обработки имени."""
    config = variant.config
    name = (f"{Path(variant.records_path).parent.name}_{file_fingerprint(variant.records_path)}_"
            f"{config.embedding_model}_{config.chunk_size}_{config.chunk_overlap}_{config.site}")
    if config.strip_owner_name:
        name += "_noname"
    return Path(cache_dir) / name


def get_variant_index(variant: Variant, client: Any,
                      cache_dir: str | Path = DEFAULT_CACHE_DIR) -> tuple[Any, list[dict[str, Any]]]:
    """Загружает индекс варианта из кэша или строит и сохраняет новый."""
    directory = index_dir_for(variant, cache_dir)
    if (directory / "index.faiss").exists():
        index, chunks, _ = load_index(directory)
        return index, chunks
    index, chunks = build_knowledge_index(client, variant.config, variant.records_path,
                                          require_verified=variant.require_verified)
    save_index(index, chunks, variant.config, directory)
    return index, chunks


def describe_hits(log: dict[str, Any], chunks: list[dict[str, Any]], cited: list[int]) -> str:
    """Все найденные фрагменты: номер, ✓ у процитированных, сходство, запись и заголовок."""
    by_id = {chunk["chunk_id"]: chunk for chunk in chunks}
    lines = []
    for number, hit in enumerate(log.get("hits", []), start=1):
        chunk = by_id.get(hit["chunk_id"], {})
        mark = "✓" if number in cited else " "
        lines.append(f"[{number}] {mark} {hit['score']:.3f} {hit['chunk_id']} — {chunk.get('title', '')}")
    return "\n".join(lines)


def run_question(question: dict[str, Any], variant: Variant, repeat: int, client: Any, index: Any,
                 chunks: list[dict[str, Any]], prompts: dict[str, Any],
                 keywords: dict[str, str] | None = None) -> dict[str, Any]:
    """Задаёт один вопрос одному варианту и возвращает строку результата."""
    row = {**question, "variant": variant.name, "repeat": repeat, "status": "", "intent": "",
           "search_query": "", "embedded_query": "", "answer": "", "cited": "", "fragments": "",
           "top_score": None, "duration_sec": None, "error": ""}
    try:
        response = run_assistant(question["question"], client, index, chunks, variant.config, prompts, keywords)
    except AssistantError as exc:
        row.update(status="error", error=str(exc))
        return row
    log = response.log
    cited = [source["number"] for source in response.sources]
    hits = log.get("hits", [])
    row.update(
        status=response.status,
        intent=log.get("intent", {}).get("intent", "") + (
            f" → {log['kb_term_override']['category']} (ключевое слово «{log['kb_term_override']['keyword']}»)"
            if log.get("kb_term_override") else ""),
        search_query=log.get("intent", {}).get("search_query", ""),
        embedded_query=log.get("embedded_query", ""),
        answer=response.answer,
        cited="\n".join(f"[{s['number']}] {s['title']} ({s['record_id']})" for s in response.sources),
        fragments=describe_hits(log, chunks, cited),
        top_score=max((h["score"] for h in hits), default=None),
        duration_sec=log.get("duration_sec"),
    )
    return row


def run_batch(questions: list[dict[str, Any]], variants: list[Variant], client: Any,
              cache_dir: str | Path = DEFAULT_CACHE_DIR, prompts_dir: str | Path = DEFAULT_PROMPTS_DIR,
              repeats: int = 1, max_consecutive_errors: int = 3,
              on_row: Callable[[list[dict[str, Any]]], None] | None = None) -> tuple[list[dict[str, Any]], str]:
    """Прогоняет все вопросы через все варианты repeats раз.

    Возвращает строки результатов и причину остановки ("" — прогон завершён).
    on_row вызывается после каждой строки со всеми строками на этот момент,
    например чтобы сохранять таблицу по ходу прогона.
    """
    rows: list[dict[str, Any]] = []
    consecutive_errors = 0
    for variant in variants:
        try:
            index, chunks = get_variant_index(variant, client, cache_dir)
        except AssistantError as exc:
            return rows, f"Не удалось построить индекс для {variant.name}: {exc}"
        prompts = load_prompts(variant.config, prompts_dir)
        keywords = load_keywords(variant.keywords_path) if variant.keywords_path else None
        for repeat in range(1, repeats + 1):
            for question in questions:
                row = run_question(question, variant, repeat, client, index, chunks, prompts, keywords)
                rows.append(row)
                if on_row:
                    on_row(rows)
                consecutive_errors = consecutive_errors + 1 if row["status"] == "error" else 0
                if consecutive_errors >= max_consecutive_errors:
                    return rows, f"Остановлено после {consecutive_errors} ошибок подряд: {row['error']}"
    return rows, ""


# ---------------------------------------------------------------------------
# Запись в Excel
# ---------------------------------------------------------------------------

RESULT_COLUMNS = [
    ("№", "no", 6), ("Тип вопроса", "type", 14), ("Вопрос", "question", 40), ("Вариант", "variant", 16),
    ("Повтор", "repeat", 8), ("Статус", "status", 18), ("Намерение", "intent", 12),
    ("Поисковый запрос", "search_query", 30), ("Запрос для эмбеддинга", "embedded_query", 30),
    ("Ответ", "answer", 70), ("Процитированные источники", "cited", 40), ("Найденные фрагменты", "fragments", 60),
    ("Макс. сходство", "top_score", 10), ("Время, с", "duration_sec", 9), ("Ошибка", "error", 30),
    ("Ожидаемые факты", "expected", 45), ("Правильное поведение", "behaviour", 20),
    ("Оценка (0–2)", "score", 10), ("Выдумка (да/нет)", "fabrication", 10), ("Комментарий", "comment", 40),
]
MANUAL_KEYS = {"score", "fabrication", "comment"}

HEADER_FONT = Font(name="Arial", bold=True, color="FFFFFF")
HEADER_FILL = PatternFill("solid", fgColor="305496")
INPUT_FILL = PatternFill("solid", fgColor="FFF2CC")
BODY_FONT = Font(name="Arial", size=10)
WRAP = Alignment(wrap_text=True, vertical="top")


def _header(worksheet, titles: list[str], widths: list[int]) -> None:
    for column, (title, width) in enumerate(zip(titles, widths), start=1):
        cell = worksheet.cell(row=1, column=column, value=title)
        cell.font, cell.fill, cell.alignment = HEADER_FONT, HEADER_FILL, WRAP
        worksheet.column_dimensions[get_column_letter(column)].width = width
    worksheet.freeze_panes = "A2"


def _write_results_sheet(worksheet, rows: list[dict[str, Any]]) -> None:
    _header(worksheet, [c[0] for c in RESULT_COLUMNS], [c[2] for c in RESULT_COLUMNS])
    for number, row in enumerate(rows, start=2):
        for column, (_, key, _) in enumerate(RESULT_COLUMNS, start=1):
            value = row.get(key)
            cell = worksheet.cell(row=number, column=column)
            if isinstance(value, str):
                # Текст, начинающийся с «=», Excel принял бы за формулу.
                cell.value, cell.data_type = value, "s"
            else:
                cell.value = value
            cell.font, cell.alignment = BODY_FONT, WRAP
            if key in MANUAL_KEYS:
                cell.fill = INPUT_FILL
    last = max(len(rows) + 1, 2)
    keys = [c[1] for c in RESULT_COLUMNS]
    score = get_column_letter(keys.index("score") + 1)
    fabrication = get_column_letter(keys.index("fabrication") + 1)
    score_rule = DataValidation(type="list", formula1='"0,1,2"', allow_blank=True)
    fabrication_rule = DataValidation(type="list", formula1='"да,нет"', allow_blank=True)
    worksheet.add_data_validation(score_rule)
    worksheet.add_data_validation(fabrication_rule)
    score_rule.add(f"{score}2:{score}{last}")
    fabrication_rule.add(f"{fabrication}2:{fabrication}{last}")
    worksheet.auto_filter.ref = f"A1:{get_column_letter(len(RESULT_COLUMNS))}{last}"


def _write_summary_sheet(worksheet, variants: list[Variant], last_row: int) -> None:
    keys = [c[1] for c in RESULT_COLUMNS]

    def col(key: str) -> str:
        letter = get_column_letter(keys.index(key) + 1)
        return f"'Результаты'!${letter}$2:${letter}${max(last_row, 2)}"

    titles = ["Вариант", "Описание", "Ответов", "Оценено", "Средняя оценка", "Выдумок"] + \
             [f"Статус: {s}" for s in STATUSES] + ["Среднее время, с"]
    _header(worksheet, titles, [16, 45, 9, 9, 10, 9] + [12] * len(STATUSES) + [10])
    variant_col, score_col, fab_col = col("variant"), col("score"), col("fabrication")
    status_col, time_col = col("status"), col("duration_sec")
    for number, variant in enumerate(variants, start=2):
        a = f"$A{number}"
        values = [
            variant.name, variant.description,
            f"=COUNTIF({variant_col},{a})",
            f'=COUNTIFS({variant_col},{a},{score_col},"<>")',
            f'=IFERROR(ROUND(AVERAGEIFS({score_col},{variant_col},{a}),2),"")',
            f'=COUNTIFS({variant_col},{a},{fab_col},"да")',
        ] + [f'=COUNTIFS({variant_col},{a},{status_col},"{s}")' for s in STATUSES] + [
            f'=IFERROR(ROUND(AVERAGEIFS({time_col},{variant_col},{a}),2),"")',
        ]
        for column, value in enumerate(values, start=1):
            cell = worksheet.cell(row=number, column=column, value=value)
            cell.font, cell.alignment = BODY_FONT, WRAP
    note_row = len(variants) + 3
    worksheet.cell(row=note_row, column=1,
                   value="Средняя оценка и число выдумок считаются по заполненным жёлтым столбцам листа «Результаты».").font = BODY_FONT


def _write_settings_sheet(worksheet, variants: list[Variant], meta: dict[str, Any]) -> None:
    config_keys = list(asdict(AssistantConfig()).keys())
    titles = ["Вариант", "Описание", "База знаний", "Хэш файла базы", "Только проверенные записи",
              "Таблица ключевых слов"] + config_keys
    _header(worksheet, titles, [16, 45, 40, 14, 12, 30] + [14] * len(config_keys))
    for number, variant in enumerate(variants, start=2):
        config = asdict(variant.config)
        values = [variant.name, variant.description, str(variant.records_path),
                  file_fingerprint(variant.records_path), "да" if variant.require_verified else "нет",
                  str(variant.keywords_path or "")]
        values += [str(config[key]) for key in config_keys]
        for column, value in enumerate(values, start=1):
            cell = worksheet.cell(row=number, column=column)
            cell.value, cell.data_type = value, "s"
            cell.font, cell.alignment = BODY_FONT, WRAP
    row = len(variants) + 3
    for key, value in meta.items():
        worksheet.cell(row=row, column=1, value=key).font = Font(name="Arial", bold=True)
        cell = worksheet.cell(row=row, column=2)
        cell.value, cell.data_type, cell.font = str(value), "s", BODY_FONT
        row += 1


def _write_criteria_sheet(worksheet) -> None:
    lines = [
        ("Шкала оценки", ""),
        ("2", "Верно и полно: все ожидаемые факты, ничего лишнего; правильное поведение (ответ, поправка или отказ)."),
        ("1", "Частично: неполно или есть неточность, взятая из контекста."),
        ("0", "Неверно: факт противоречит ожидаемому, неправильное поведение (ответил вместо отказа, "
              "согласился с ложной посылкой) или есть выдуманный факт."),
        ("Выдумка — да", "В ответе есть утверждение, которого нет в найденных фрагментах (галлюцинация)."),
        ("Статус error", "Ошибка провайдера LLM или невалидный ответ модели; текст ошибки — в столбце «Ошибка»."),
        ("Как заполнять", "Жёлтые столбцы листа «Результаты»: оценка 0/1/2, выдумка да/нет, комментарий."),
    ]
    worksheet.column_dimensions["A"].width = 18
    worksheet.column_dimensions["B"].width = 100
    for number, (key, text) in enumerate(lines, start=1):
        worksheet.cell(row=number, column=1, value=key).font = Font(name="Arial", bold=True)
        cell = worksheet.cell(row=number, column=2, value=text)
        cell.font, cell.alignment = BODY_FONT, WRAP


def write_results(rows: list[dict[str, Any]], variants: list[Variant], output_path: str | Path,
                  meta: dict[str, Any] | None = None) -> Path:
    """Сохраняет результаты прогона: листы «Результаты», «Сводка», «Настройки», «Критерии»."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    results = workbook.active
    results.title = "Результаты"
    _write_results_sheet(results, rows)
    _write_summary_sheet(workbook.create_sheet("Сводка"), variants, len(rows) + 1)
    _write_settings_sheet(workbook.create_sheet("Настройки"), variants, meta or {})
    _write_criteria_sheet(workbook.create_sheet("Критерии"))
    workbook.save(output_path)
    return output_path


def run_meta(questions_path: str | Path, questions: list[dict[str, Any]], repeats: int,
             stop_reason: str = "", started: datetime | None = None) -> dict[str, Any]:
    """Сведения о прогоне для листа «Настройки»."""
    return {
        "Дата прогона": (started or datetime.now()).strftime("%d.%m.%Y %H:%M"),
        "Файл вопросов": str(questions_path),
        "Вопросов": len(questions),
        "Повторов": repeats,
        "Итог": stop_reason or "Прогон завершён",
    }
