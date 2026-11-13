"""Собирает ноутбук-прототип этапа 3 из модуля app/rag/assistant_core.py.

Код функций переносится в ячейки ноутбука без изменений, поэтому ноутбук и сайт
всегда используют одну и ту же реализацию. Меняются только пути по умолчанию:
в ноутбуке все файлы лежат в одной папке с ним.

Запуск:
    python scripts/build_notebook.py
    python scripts/build_notebook.py --zip-url "https://drive.google.com/file/d/.../view?usp=sharing"

Результат — папка notebooks/stage3_prototype/:
    assistant_stage3.ipynb   ноутбук
    records_rag_a.jsonl      база RAG A
    records_rag_b1.jsonl     база RAG B1 (страницы сайта)
    records_rag_b2.jsonl     база RAG B2 (страницы и PDF сайта)
    prompts/ru/...           промпты
    README.md                как запустить
и архив notebooks/stage3_prototype_data.zip (базы знаний и промпты) для загрузки на Google Drive.
В Colab ноутбук скачивает этот архив по общедоступной ссылке и распаковывает в /content.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CORE_PATH = ROOT_DIR / "app" / "rag" / "assistant_core.py"
OUTPUT_DIR = ROOT_DIR / "notebooks" / "stage3_prototype"
NOTEBOOK_NAME = "assistant_stage3.ipynb"
ZIP_PATH = ROOT_DIR / "notebooks" / "stage3_prototype_data.zip"
DEFAULT_ZIP_URL = "https://drive.google.com/file/d/1WyBsx_Xeo_NqXfM5TJHUfAQxdYYpdHhV/view?usp=sharing"  # архив на Google Drive (доступ по ссылке)

DATA_FILES = {
    ROOT_DIR / "knowledge_base" / "rag_a" / "records.jsonl": "records_rag_a.jsonl",
    ROOT_DIR / "knowledge_base" / "rag_b" / "records.jsonl": "records_rag_b1.jsonl",
    ROOT_DIR / "knowledge_base" / "rag_b2" / "records.jsonl": "records_rag_b2.jsonl",
}

CORE_PATHS_IN_MODULE = '''PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECORDS_PATH = PROJECT_ROOT / "knowledge_base" / "rag_a" / "records.jsonl"
DEFAULT_PROMPTS_DIR = PROJECT_ROOT / "prompts"
DEFAULT_INDEX_DIR = PROJECT_ROOT / "rag" / "index_rag_a"'''

CORE_PATHS_IN_NOTEBOOK = '''DATA_ZIP_URL = "{zip_url}"  # общедоступная ссылка Google Drive на архив с данными
COLAB_DATA_DIR = Path("/content/stage3_prototype")


def download_data(zip_url: str = DATA_ZIP_URL, target_dir: Path = COLAB_DATA_DIR) -> Path:
    """Скачивает архив с базами знаний и промптами по ссылке и распаковывает его в target_dir.

    Если данные уже распакованы в этой сессии Colab, повторно архив не скачивается.
    """
    import zipfile

    if (target_dir / "records_rag_a.jsonl").exists():
        return target_dir
    if not zip_url:
        raise ValueError("Не задана ссылка DATA_ZIP_URL на архив stage3_prototype_data.zip")
    import gdown  # установлен в Google Colab; скачивает файлы Google Drive по ссылке «доступ по ссылке»

    target_dir.mkdir(parents=True, exist_ok=True)
    archive = target_dir.parent / "stage3_prototype_data.zip"
    if not gdown.download(zip_url, str(archive), quiet=True, fuzzy=True):
        raise RuntimeError(f"Не удалось скачать архив: {{zip_url}}. Проверьте, что у файла включён доступ по ссылке.")
    with zipfile.ZipFile(archive) as zip_file:
        zip_file.extractall(target_dir)
    return target_dir


def data_dir_for_environment(zip_url: str = DATA_ZIP_URL, colab_dir: Path = COLAB_DATA_DIR) -> Path:
    """Папка с файлами ноутбука: в Google Colab — распакованный архив, локально — текущая папка."""
    try:
        import google.colab  # noqa: F401  (модуль есть только в Google Colab)
    except ImportError:
        return Path(".")
    return download_data(zip_url, colab_dir)


DATA_DIR = data_dir_for_environment()  # папка, в которой лежат базы знаний и промпты
print(f"Папка с файлами ноутбука: {{DATA_DIR.resolve()}}")
DEFAULT_RECORDS_PATH = DATA_DIR / "records_rag_a.jsonl"
DEFAULT_PROMPTS_DIR = DATA_DIR / "prompts"
DEFAULT_INDEX_DIR = DATA_DIR / "index" / "rag_a"'''

INTRO_MD = """# Прототип AI-ассистента персонального сайта (этап 3)

**Тема:** персональный сайт с AI-ассистентом для представления профессиональных компетенций.
**Автор:** Андрис Янчевскис.

Ассистент отвечает на вопросы посетителей (рекрутеров, работодателей, заказчиков) об опыте Андриса
только по внешней базе знаний (RAG). Исследовательский вопрос: даёт ли **редактируемая база знаний (RAG A)**
более точные и честные ответы, чем база, полученная **парсингом страниц сайта (RAG B1)** или
**страниц и PDF-файлов сайта (RAG B2)**. Код ассистента одинаков для всех баз, меняется только база.

## Схема работы

```
вопрос
  │
  ▼
[LLM-вызов 1] detect_intent ──► намерение + поисковый запрос
  │                              (off_topic → вежливый отказ без поиска)
  ▼
[RAG] embed_texts + search ──► top_k фрагментов базы знаний (FAISS)
  │                              (нет фрагментов выше порога → отказ)
  ▼
[LLM-вызов 2] generate_answer ─► ответ только по найденным фрагментам,
                                 номера источников, признак достаточности
```

## Как запустить

1. Откройте ноутбук в Google Colab. Базы знаний и промпты скачиваются автоматически по ссылке
   на архив `stage3_prototype_data.zip` и распаковываются в `/content/stage3_prototype`.
   В локальном Jupyter запустите ноутбук из папки, где лежат файлы `records_*.jsonl` и папка `prompts`.
2. В Google Colab добавьте секрет `OPENAI_API_KEY` (значок ключа на левой панели) и разрешите
   ноутбуку доступ к нему. В локальном Jupyter задайте переменную окружения `OPENAI_API_KEY`.
3. Выполните ячейки по порядку. В последней ячейке запускается `main()`: введите вопрос и базу
   знаний — `A`, `B1`, `B2` или `ALL` для сравнения.
4. Индексы FAISS строятся при первом запуске и сохраняются в папку `index/`; повторно эмбеддинги
   не создаются.

Ключ в ноутбуке не хранится. Ответы без ключа не подставляются: при ошибке API выводится
честное сообщение об ошибке.
"""

SETUP_MD = """## 1. Подготовка окружения

Установка библиотек. Файлы баз знаний и промпты в Google Colab скачиваются автоматически
в следующей ячейке по ссылке на архив; подключать Google Drive не нужно."""

SETUP_CODE = """%pip install -q faiss-cpu openai pydantic numpy gdown"""

CELL_NOTES = {
    "imports": "## 2. Импорт библиотек и пути к файлам\n\nВсе пути — параметры функций со значениями по умолчанию относительно папки ноутбука.",
    "Настройки и структуры данных": "## 3. Настройки и структуры данных\n\n`AssistantConfig` собирает все параметры, которые меняются в экспериментах. Pydantic-модели проверяют ответы LLM на каждом шаге.",
    "1. База знаний": "## 4. База знаний и чанкинг\n\nЗагрузка записей (для RAG A — только `verified` и `public`), деление текста на фрагменты с перекрытием.",
    "2. Эмбеддинги и векторный индекс FAISS": "## 5. Эмбеддинги и векторный индекс FAISS\n\nЭмбеддинги OpenAI, L2-нормализация и индекс `IndexFlatIP` (точный поиск по косинусному сходству).",
    "3. Промпты и два обращения к LLM": "## 6. Промпты и два обращения к LLM\n\nПромпт 1 определяет намерение и формирует поисковый запрос, промпт 2 отвечает только по найденному контексту. Тексты промптов лежат в папке `prompts/` и имеют версии.",
    "4. Главная функция": "## 7. Обработка одного вопроса\n\n`run_assistant` выполняет шаги по схеме и возвращает ответ, статус, источники и журнал шагов.",
}

NOTEBOOK_FUNCTIONS = '''CORPORA = {
    "A": {"file": "records_rag_a.jsonl", "require_verified": True, "title": "RAG A — редактируемая база знаний"},
    "B1": {"file": "records_rag_b1.jsonl", "require_verified": False, "title": "RAG B1 — парсинг страниц сайта"},
    "B2": {"file": "records_rag_b2.jsonl", "require_verified": False, "title": "RAG B2 — страницы и PDF сайта"},
}


def index_dir_for(corpus: str, config: AssistantConfig, data_dir: str | Path = DATA_DIR) -> Path:
    """Папка индекса: своя для каждой базы, модели эмбеддингов и параметров чанкинга."""
    name = f"{corpus}_{config.embedding_model}_{config.chunk_size}_{config.chunk_overlap}"
    return Path(data_dir) / "index" / name


def get_corpus_index(corpus: str, client: Any, config: AssistantConfig, corpora: dict = CORPORA,
                     data_dir: str | Path = DATA_DIR) -> tuple[Any, list[dict[str, Any]]]:
    """Загружает сохранённый индекс базы или строит и сохраняет новый."""
    directory = index_dir_for(corpus, config, data_dir)
    if (directory / "index.faiss").exists():
        index, chunks, _ = load_index(directory)
        return index, chunks
    settings = corpora[corpus]
    index, chunks = build_knowledge_index(client, config, Path(data_dir) / settings["file"],
                                          require_verified=settings["require_verified"])
    save_index(index, chunks, config, directory)
    return index, chunks


def ask(question: str, corpus_names: list[str], client: Any, config: AssistantConfig, prompts: dict[str, Any],
        corpora: dict = CORPORA, data_dir: str | Path = DATA_DIR) -> dict[str, AssistantResponse | str]:
    """Задаёт один вопрос ассистенту с каждой из выбранных баз знаний."""
    results: dict[str, AssistantResponse | str] = {}
    for corpus in corpus_names:
        try:
            index, chunks = get_corpus_index(corpus, client, config, corpora, data_dir)
            results[corpus] = run_assistant(question, client, index, chunks, config, prompts)
        except AssistantError as exc:
            results[corpus] = f"Ошибка: {exc}"
    return results


def format_result(corpus: str, result: AssistantResponse | str, corpora: dict = CORPORA) -> str:
    """Готовит понятный текст результата для вывода."""
    lines = [f"=== {corpora[corpus]['title']} ==="]
    if isinstance(result, str):
        return "\\n".join(lines + [result])
    lines.append(f"Статус: {result.status}")
    lines.append(result.answer)
    hits = result.log.get("hits", [])
    if hits:
        cited = {source["number"]: source for source in result.sources}
        lines.append("  Фрагменты, переданные модели (✓ — модель сослалась на него в ответе):")
        for number, hit in enumerate(hits, start=1):
            mark = "✓" if number in cited else " "
            title = f" — {cited[number]['title']} ({cited[number]['source_url']})" if number in cited else ""
            lines.append(f"   {mark} [{number}] {hit['chunk_id']} (сходство {hit['score']}){title}")
    return "\\n".join(lines)


def read_api_key(secret_name: str = "OPENAI_API_KEY") -> str:
    """Читает ключ OpenAI API из секретов Google Colab, вне Colab — из переменной окружения."""
    import os

    try:
        from google.colab import userdata  # доступно только в Google Colab
        key = userdata.get(secret_name)
    except ImportError:
        key = os.environ.get(secret_name)
    if not key:
        raise RuntimeError(
            f"Ключ не найден. В Colab добавьте секрет {secret_name} (значок ключа слева) и разрешите "
            f"ноутбуку доступ к нему; вне Colab задайте переменную окружения {secret_name}."
        )
    return key


def create_client(api_key: str | None = None) -> Any:
    """Создаёт клиента OpenAI; без параметра ключ читается функцией read_api_key."""
    from openai import OpenAI

    return OpenAI(api_key=api_key or read_api_key())


def main(data_dir: str | Path = DATA_DIR, config: AssistantConfig | None = None, corpora: dict = CORPORA) -> None:
    """Тестовая функция: вопросы вводятся с клавиатуры, ответы выводятся по выбранным базам."""
    config = config or AssistantConfig()
    client = create_client()
    prompts = load_prompts(config, Path(data_dir) / "prompts")
    print("Пустой вопрос завершает работу.")
    while True:
        question = input("\\nВопрос: ").strip()
        if not question:
            break
        choice = (input(f"База знаний ({', '.join(corpora)} или ALL) [ALL]: ").strip().upper() or "ALL")
        names = list(corpora) if choice == "ALL" else [choice]
        if any(name not in corpora for name in names):
            print(f"Неизвестная база: {choice}")
            continue
        for corpus, result in ask(question, names, client, config, prompts, corpora, data_dir).items():
            print()
            print(format_result(corpus, result, corpora))'''

MAIN_MD = """## 8. Функции ноутбука и тестовый запуск

`ask` задаёт вопрос с выбранными базами, `main` — главная функция: берёт ключ API из секретов Colab
(`OPENAI_API_KEY`), запрашивает вопрос и базу знаний и выводит ответы. Для сравнения баз введите `ALL`."""

README = """# Прототип AI-ассистента (этап 3)

Папка создана скриптом `scripts/build_notebook.py` из модуля `app/rag/assistant_core.py`.
Не редактируйте ноутбук вручную: измените модуль и пересоберите папку.

- `assistant_stage3.ipynb` — ноутбук-прототип; последняя ячейка запускает `main()`.
- `records_rag_a.jsonl` — редактируемая база знаний (RAG A).
- `records_rag_b1.jsonl` — база, полученная парсингом страниц сайта (RAG B1).
- `records_rag_b2.jsonl` — страницы сайта и PDF-файлы сайта (RAG B2).
- `prompts/ru/` — промпты двух вызовов LLM и служебные сообщения.

В Google Colab базы знаний и промпты скачиваются по ссылке на архив `stage3_prototype_data.zip`
(создаётся тем же скриптом в папке `notebooks/`).

Ключ OpenAI API берётся из секрета Google Colab `OPENAI_API_KEY` (вне Colab — из переменной окружения
с тем же именем) и в ноутбуке не хранится.
"""


def split_core_sections(source: str) -> list[tuple[str, str]]:
    """Делит модуль на части по заголовкам-разделителям «# ----- / # Название / # -----»."""
    pattern = re.compile(r"^# -{20,}\n# (.+)\n# -{20,}\n", re.MULTILINE)
    matches = list(pattern.finditer(source))
    sections = [("imports", source[:matches[0].start()])]
    for current, following in zip(matches, matches[1:] + [None]):
        end = following.start() if following else len(source)
        sections.append((current.group(1).strip(), source[current.end():end]))
    return sections


def prepare_imports(header: str, zip_url: str = DEFAULT_ZIP_URL) -> str:
    """Убирает docstring модуля и __future__-импорт, подставляет пути ноутбука."""
    body = header.split('"""', 2)[2] if header.lstrip().startswith('"""') else header
    body = body.replace("from __future__ import annotations\n", "")
    if CORE_PATHS_IN_MODULE not in body:
        raise ValueError("Не найден блок путей в assistant_core.py — обновите build_notebook.py")
    return body.replace(CORE_PATHS_IN_MODULE, CORE_PATHS_IN_NOTEBOOK.format(zip_url=zip_url)).strip()


def cell(kind: str, text: str, number: int) -> dict:
    """Ячейка ноутбука в формате nbformat 4.5."""
    lines = text.strip("\n").splitlines(keepends=True)
    data = {"cell_type": kind, "id": f"cell-{number:02d}", "metadata": {}, "source": lines}
    if kind == "code":
        data.update({"execution_count": None, "outputs": []})
    return data


def build_cells(core_source: str, zip_url: str = DEFAULT_ZIP_URL) -> list[dict]:
    """Список ячеек: описание, подготовка, код модуля по разделам, функции ноутбука, main()."""
    blocks: list[tuple[str, str]] = [("markdown", INTRO_MD), ("markdown", SETUP_MD), ("code", SETUP_CODE)]
    for title, code in split_core_sections(core_source):
        blocks.append(("markdown", CELL_NOTES[title]))
        blocks.append(("code", prepare_imports(code, zip_url) if title == "imports" else code.strip()))
    blocks += [("markdown", MAIN_MD), ("code", NOTEBOOK_FUNCTIONS),
               ("markdown", "## 9. Тестовая ячейка\n\nЗапустите и введите свой вопрос."), ("code", "main()")]
    return [cell(kind, text, number) for number, (kind, text) in enumerate(blocks, start=1)]


def build_data_zip(data_dir: Path = OUTPUT_DIR, zip_path: Path = ZIP_PATH) -> Path:
    """Упаковывает базы знаний и промпты в архив для Google Drive (без ноутбука и индексов)."""
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for name in DATA_FILES.values():
            if (data_dir / name).exists():
                zip_file.write(data_dir / name, name)
        for prompt in sorted((data_dir / "prompts").rglob("*")):
            if prompt.is_file():
                zip_file.write(prompt, prompt.relative_to(data_dir).as_posix())
    return zip_path


def build_notebook(output_dir: Path = OUTPUT_DIR, zip_url: str = DEFAULT_ZIP_URL) -> Path:
    """Создаёт папку с ноутбуком, базами знаний и промптами, и архив с данными."""
    output_dir.mkdir(parents=True, exist_ok=True)
    notebook = {
        "cells": build_cells(CORE_PATH.read_text(encoding="utf-8"), zip_url),
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    path = output_dir / NOTEBOOK_NAME
    path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    missing = []
    for source, name in DATA_FILES.items():
        if source.exists():
            shutil.copyfile(source, output_dir / name)
        else:
            missing.append(str(source))
    prompts_target = output_dir / "prompts"
    if prompts_target.exists():
        shutil.rmtree(prompts_target)
    shutil.copytree(ROOT_DIR / "prompts", prompts_target)
    (output_dir / "README.md").write_text(README, encoding="utf-8")
    archive = build_data_zip(output_dir)

    print(f"Ноутбук: {path}")
    print(f"Архив с данными для Google Drive: {archive}")
    if not zip_url:
        print("Ссылка на архив не задана: загрузите архив на Drive, откройте доступ по ссылке "
              "и запустите скрипт с параметром --zip-url")
    for name in missing:
        print(f"Внимание: нет файла {name} — соберите базу и запустите скрипт снова")
    return path


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cli = argparse.ArgumentParser(description="Сборка ноутбука этапа 3")
    cli.add_argument("--zip-url", default=DEFAULT_ZIP_URL, help="ссылка Google Drive на stage3_prototype_data.zip")
    build_notebook(zip_url=cli.parse_args().zip_url)
