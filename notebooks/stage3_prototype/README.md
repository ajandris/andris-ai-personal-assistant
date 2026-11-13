# Прототип AI-ассистента (этап 3)

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
