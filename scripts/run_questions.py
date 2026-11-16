"""Пакетный прогон тестовых вопросов через варианты ассистента с записью в Excel.

Примеры (из корня проекта):

    # список готовых вариантов
    python scripts/run_questions.py --list-variants

    # 15 вопросов этапа 3 по всем вариантам, результат — в папку диплома
    python scripts/run_questions.py --output "Q:/Actual/Studijas/Institut II/AI Agent course/Diploma/Etap_4_progon_15.xlsx"

    # те же вопросы и варианты с перекрытием фрагментов 0 (индексы FAISS строятся заново)
    python scripts/run_questions.py --chunk-overlap 0 --output ".../Diploma/Etap_4_progon_15_overlap0.xlsx"

    # «чистый» прогон: оба вызова LLM с температурой 0, перекрытие 0
    python scripts/run_questions.py --chunk-overlap 0 --answer-temperature 0 --output ".../Diploma/Etap_4_progon_15_t0.xlsx"

    # только два варианта и вопросы 4, 13, 14
    python scripts/run_questions.py --variants A_v1 A_p2 --questions-ids 4 13 14 --output result.xlsx

Ключ OpenAI API берётся из переменной окружения OPENAI_API_KEY или из файла .env
в корне проекта. Таблица сохраняется после каждого ответа, поэтому при остановке
прогона уже полученные результаты не теряются.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv  # noqa: E402

from app.rag.batch_runner import (  # noqa: E402
    DEFAULT_CACHE_DIR,
    DEFAULT_QUESTIONS_PATH,
    default_variants,
    load_questions,
    run_batch,
    run_meta,
    select_questions,
    with_config_overrides,
    write_results,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    variants = default_variants()
    parser = argparse.ArgumentParser(description="Пакетный прогон вопросов с записью результатов в Excel")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS_PATH,
                        help="Excel-файл с вопросами (столбцы «№», «Вопрос», необязательно «Тип вопроса», "
                             "«Ожидаемые факты», «Правильное поведение»)")
    parser.add_argument("--sheet", default=None, help="Лист с вопросами (по умолчанию первый)")
    parser.add_argument("--variants", nargs="+", default=list(variants), choices=list(variants),
                        metavar="NAME", help="Варианты ассистента (по умолчанию все)")
    parser.add_argument("--questions-ids", nargs="+", default=None, metavar="N", help="Только вопросы с этими номерами")
    parser.add_argument("--limit", type=int, default=None, help="Только первые N вопросов")
    parser.add_argument("--repeats", type=int, default=1, help="Сколько раз задать каждый вопрос каждому варианту")
    parser.add_argument("--chunk-overlap", type=int, default=None,
                        help="Перекрытие фрагментов для всех вариантов (по умолчанию — из AssistantConfig, 0)")
    parser.add_argument("--chunk-size", type=int, default=None,
                        help="Длина фрагмента для всех вариантов (по умолчанию — из AssistantConfig, 800)")
    parser.add_argument("--answer-temperature", type=float, default=None,
                        help="Температура второго вызова LLM для всех вариантов (по умолчанию — из AssistantConfig, 0.0)")
    parser.add_argument("--intent-temperature", type=float, default=None,
                        help="Температура первого вызова LLM для всех вариантов (по умолчанию — из AssistantConfig, 0.0)")
    parser.add_argument("--output", type=Path, help="Куда сохранить таблицу .xlsx")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR, help="Папка кэша индексов FAISS")
    parser.add_argument("--list-variants", action="store_true", help="Показать варианты и выйти")
    args = parser.parse_args(argv)
    if not args.list_variants and not args.output:
        parser.error("укажите --output")
    return args


def create_client(env_file: Path = ROOT_DIR / ".env"):
    """Клиент OpenAI с ключом из окружения или .env."""
    from openai import OpenAI

    if env_file.exists():
        load_dotenv(env_file, encoding="utf-8")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Не задан OPENAI_API_KEY (переменная окружения или файл .env в корне проекта)")
    return OpenAI(api_key=api_key)


def main(argv: list[str] | None = None) -> int:
    # Вывод скрипта на русском: в Windows при выводе в файл или канал Python по
    # умолчанию берёт кодировку cp1252 без кириллицы. Явно задаём UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(argv)
    all_variants = default_variants()
    if args.list_variants:
        for name, variant in all_variants.items():
            print(f"{name:14} {variant.description}")
        return 0

    questions = select_questions(load_questions(args.questions, args.sheet), args.questions_ids, args.limit)
    if not questions:
        raise SystemExit("Не выбрано ни одного вопроса")
    overrides = {key: value for key, value in (("chunk_overlap", args.chunk_overlap),
                                               ("chunk_size", args.chunk_size),
                                               ("answer_temperature", args.answer_temperature),
                                               ("intent_temperature", args.intent_temperature)) if value is not None}
    variants = with_config_overrides([all_variants[name] for name in args.variants], **overrides)
    if overrides:
        print("Изменённые параметры для всех вариантов:", overrides)
    total = len(questions) * len(variants) * args.repeats
    started = datetime.now()
    client = create_client()
    print(f"Вопросов: {len(questions)}, вариантов: {len(variants)}, повторов: {args.repeats} — всего ответов: {total}")

    def save(rows):
        write_results(rows, variants, args.output, run_meta(args.questions, questions, args.repeats, "Прогон идёт", started))
        last = rows[-1]
        print(f"[{len(rows)}/{total}] {last['variant']} — вопрос {last['no']}: {last['status']}")

    rows, stop_reason = run_batch(questions, variants, client, args.cache_dir, repeats=args.repeats, on_row=save)
    write_results(rows, variants, args.output, run_meta(args.questions, questions, args.repeats, stop_reason, started))
    print(f"Сохранено: {args.output}")
    if stop_reason:
        print(stop_reason)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
