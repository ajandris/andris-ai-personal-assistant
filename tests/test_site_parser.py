"""Тесты парсера сайта для корпуса RAG B (без сети и без API-ключа)."""

import json

import pytest

from app.rag.assistant_core import load_records
from app.rag.site_parser import DEFAULT_PAGES, extract_sections, page_key, sections_to_records

SAMPLE_HTML = """
<html><body>
  <header><nav><a href="/">Главная</a> <a href="/skills">Навыки</a></nav></header>
  <main id="main-content">
    <section id="experience">
      <h2 class="section-title">Опыт работы</h2>
      <p>Работа в <strong>Boots</strong> с 2013 года.</p>
      <svg><path d="M0"/></svg>
      <a href="https://github.com/ajandris">Профиль GitHub</a>
      <script>console.log("секрет");</script>
    </section>
    <section id="contact">
      <h2>Контакты</h2>
      <p>Напишите через форму.</p>
      <form><label>Ваше имя</label><button>Отправить</button></form>
    </section>
  </main>
  <footer><p>© 2026 Все права защищены</p></footer>
</body></html>
"""


def test_extract_sections_takes_only_main_sections():
    sections = extract_sections(SAMPLE_HTML)
    assert [s["section_id"] for s in sections] == ["experience", "contact"]
    assert [s["title"] for s in sections] == ["Опыт работы", "Контакты"]


def test_extract_sections_drops_navigation_scripts_forms_and_footer():
    text = " ".join(s["text"] for s in extract_sections(SAMPLE_HTML))
    for unwanted in ("Главная", "секрет", "Ваше имя", "Отправить", "Все права защищены"):
        assert unwanted not in text
    assert "Работа в Boots с 2013 года." in text


def test_extract_sections_keeps_link_text_and_url():
    text = extract_sections(SAMPLE_HTML)[0]["text"]
    assert "Профиль GitHub (https://github.com/ajandris)" in text


def test_extract_sections_skips_anchor_and_mailto_links():
    html = '<main><section><p><a href="#top">Наверх</a> <a href="mailto:a@b.c">Почта</a></p></section></main>'
    text = extract_sections(html)[0]["text"]
    assert "Наверх" in text and "#top" not in text and "mailto" not in text


def test_extract_sections_removes_emoji_and_decorative_symbols():
    html = """<main><section><h2>Услуги</h2>
      <div><span>🤖</span><h3>Прототипирование AI-ассистентов</h3></div>
      <a href="https://example.com/repo">GitHub<span>↗</span></a>
      <p>Открыть опыт →</p><p>✦</p><p>Python • FastAPI — «проект»</p>
    </section></main>"""
    text = extract_sections(html)[0]["text"]
    for symbol in ("🤖", "↗", "→", "✦"):
        assert symbol not in text
    assert "GitHub (https://example.com/repo)" in text
    assert "Открыть опыт" in text
    assert "Python • FastAPI — «проект»" in text
    assert all(line.strip() for line in text.splitlines())


def test_page_key():
    assert page_key("/") == "home"
    assert page_key("/ai-assistant") == "ai_assistant"


def test_sections_to_records_use_rag_a_schema_and_are_unreviewed():
    records = sections_to_records(extract_sections(SAMPLE_HTML), "/experience", updated_at="2026-11-13")
    first = records[0]
    assert first["record_id"] == "rag_b_experience_experience_001"
    assert first["source_url"] == "/experience"
    assert first["verified"] is False and first["public"] is True
    assert first["verification_status"] == "unreviewed"
    assert {"record_id", "title", "content", "source_url", "language", "site"} <= set(first)


def test_rag_b_records_load_only_without_verification_requirement(tmp_path):
    path = tmp_path / "records.jsonl"
    records = sections_to_records(extract_sections(SAMPLE_HTML), "/experience")
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    assert load_records(path, site="ru") == []
    assert len(load_records(path, site="ru", require_verified=False)) == len(records)


def test_default_pages_exclude_chat_interface():
    assert "/ai-assistant" not in DEFAULT_PAGES


# --- настоящие страницы сайта (рендер через TestClient, без запуска сервера) ---

@pytest.fixture(scope="module")
def site_client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


def test_real_experience_page_is_parsed(site_client):
    sections = extract_sections(site_client.get("/experience").text)
    text = " ".join(s["text"] for s in sections)
    assert "Петробалт" in text
    assert "Warehouse operative" in text
    assert "Основная навигация" not in text  # aria-label меню не попадает в текст


def test_all_default_pages_produce_sections(site_client):
    for path in DEFAULT_PAGES:
        response = site_client.get(path)
        assert response.status_code == 200
        assert extract_sections(response.text), f"нет секций на странице {path}"


# --- вариант B2: PDF-файлы сайта ------------------------------------------------

from app.rag.site_parser import (  # noqa: E402
    extract_links,
    pdf_pages_text,
    pdf_to_records,
    remove_personal_contacts,
    same_site_pdf_links,
)


def make_pdf(text: str) -> bytes:
    """Минимальный одностраничный PDF с латинским текстом (для тестов без reportlab)."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return out


def test_extract_links_and_same_site_pdf_filter():
    html = """<main><section>
      <a href="/media/docs/CV%20RU.pdf">CV</a>
      <a href="https://github.com/ajandris/repo.pdf">чужой PDF</a>
      <a href="/experience">Опыт</a>
      <a href="/media/docs/CV%20RU.pdf">ещё раз CV</a>
    </section></main>"""
    links = extract_links(html)
    assert links == ["/media/docs/CV%20RU.pdf", "https://github.com/ajandris/repo.pdf", "/experience"]
    assert same_site_pdf_links(links, "http://127.0.0.1:8200/contact") == [
        "http://127.0.0.1:8200/media/docs/CV%20RU.pdf"
    ]


def test_remove_personal_contacts():
    text = "Andris - 07752 194 449 - andris.test@example.com; 1999 - 2002"
    cleaned = remove_personal_contacts(text)
    assert "07752" not in cleaned and "@" not in cleaned
    assert "1999 - 2002" in cleaned


def test_pdf_pages_text_and_records():
    data = make_pdf("Systems Analyst TietoEnator 1999")
    pages = pdf_pages_text(data)
    assert "TietoEnator" in pages[0]
    records = pdf_to_records(pages + [""], "/media/docs/Andris%20CV.pdf", updated_at="2026-11-13")
    assert len(records) == 1  # пустая страница (как у скана) не даёт записи
    assert records[0]["source_type"] == "site_pdf"
    assert records[0]["title"] == "Andris CV.pdf, стр. 1"
    assert records[0]["verified"] is False
