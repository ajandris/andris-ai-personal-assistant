"""Generate Russian version of Andris Jancevskis CV in PDF format.

The content is a faithful translation of the English CV
(media/docs/Andris Jancevskis CV October 2026 web.pdf). Personal contact
details (phone, e-mail) are intentionally not included.
"""

import sys
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


FONT_CANDIDATES = {
    # Arial on Windows (used for the published CV); DejaVu Sans on Linux as a fallback.
    "Arial": [r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "Arial-Bold": [r"C:\Windows\Fonts\arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
    "Arial-Italic": [r"C:\Windows\Fonts\ariali.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"],
    "Arial-BoldItalic": [r"C:\Windows\Fonts\arialbi.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"],
}


def register_fonts():
    for name, candidates in FONT_CANDIDATES.items():
        path = next((p for p in candidates if Path(p).exists()), None)
        if path is None:
            raise FileNotFoundError(f"No font file found for {name}: {candidates}")
        pdfmetrics.registerFont(TTFont(name, path))


def build_ru_cv_pdf(output_path: Path):
    register_fonts()

    # Page size A4 is 595.27 x 841.89 points
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=30,
        bottomMargin=30,
    )

    styles = getSampleStyleSheet()

    header_style = ParagraphStyle(
        "RunningHeader",
        fontName="Arial",
        fontSize=8.5,
        textColor=colors.HexColor("#64748b"),
        leading=11,
    )

    name_style = ParagraphStyle(
        "CandidateName",
        fontName="Arial-Bold",
        fontSize=19,
        textColor=colors.HexColor("#0f172a"),
        leading=23,
    )

    degree_style = ParagraphStyle(
        "DegreeSubtitle",
        fontName="Arial",
        fontSize=10.5,
        textColor=colors.HexColor("#1e3a8a"),
        leading=13.5,
    )

    cv_title_style = ParagraphStyle(
        "DocTitle",
        fontName="Arial-Bold",
        fontSize=11.5,
        textColor=colors.HexColor("#334155"),
        leading=15,
    )

    section_heading = ParagraphStyle(
        "SectionHeading",
        fontName="Arial-Bold",
        fontSize=10.5,
        textColor=colors.HexColor("#0f2b5c"),
        leading=14,
        spaceBefore=7,
        spaceAfter=3.5,
    )

    body_style = ParagraphStyle(
        "BodyText",
        fontName="Arial",
        fontSize=9.2,
        textColor=colors.HexColor("#1e293b"),
        leading=13,
    )

    bullet_style = ParagraphStyle(
        "BulletItem",
        fontName="Arial",
        fontSize=9.0,
        textColor=colors.HexColor("#1e293b"),
        leading=12.5,
        leftIndent=12,
    )

    role_title_style = ParagraphStyle(
        "RoleTitle",
        fontName="Arial-Bold",
        fontSize=9.2,
        textColor=colors.HexColor("#0f172a"),
        leading=13,
    )

    period_style = ParagraphStyle(
        "PeriodText",
        fontName="Arial-Bold",
        fontSize=8.8,
        textColor=colors.HexColor("#2563eb"),
        leading=12.5,
        alignment=2,  # Right aligned
    )

    story = []

    # ==========================================
    # PAGE 1
    # ==========================================

    # Running top header
    p1_header_table = Table(
        [
            [
                Paragraph("<b>АНДРИС ЯНЧЕВСКИС</b>", header_style),
                Paragraph("Стр. 1 из 2", ParagraphStyle("RightH", parent=header_style, alignment=2)),
            ]
        ],
        colWidths=[400, 123],
    )
    p1_header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(p1_header_table)
    story.append(Spacer(1, 8))

    # Name and title block
    story.append(Paragraph("Андрис Янчевскис", name_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph("BSc (Hons) Comp &amp; IT (Open)", degree_style))
    story.append(Spacer(1, 3))
    story.append(Paragraph("Резюме / Curriculum Vitae", cv_title_style))
    story.append(Spacer(1, 5))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#cbd5e1"), spaceAfter=5))

    # 1. Профессиональный профиль
    story.append(Paragraph("ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ", section_heading))
    profile_text = (
        "Высокомотивированный специалист с широкими знаниями в области IT-систем и складского дела "
        "стремится максимально использовать свой опыт и профессионально развиваться в разработке "
        "решений на основе искусственного интеллекта (AI-driven solutions)."
    )
    story.append(Paragraph(profile_text, body_style))
    story.append(Spacer(1, 5))

    # 2. Краткий опыт работы
    story.append(Paragraph("КРАТКАЯ ТРУДОВАЯ БИОГРАФИЯ", section_heading))

    boots_row = [
        Paragraph("<b>Boots Alliance — Burton Service Centre</b><br/>"
                  "<font color='#475569'>Складской работник (warehouse operative) в подразделениях DotCom Inbound, Inventory и Despatch</font>", role_title_style),
        Paragraph("Ноябрь 2013 — по наст. время", period_style),
    ]
    t1 = Table([boots_row], colWidths=[370, 153])
    t1.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t1)

    self_row = [
        Paragraph("<b>Самозанятость: строительная отрасль</b><br/>"
                  "<font color='#475569'>Руководитель команды из 10 специалистов (наружное утепление стен и штукатурные работы)</font>", role_title_style),
        Paragraph("Ноябрь 2011 — Июль 2013", period_style),
    ]
    t2 = Table([self_row], colWidths=[370, 153])
    t2.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t2)

    latvia_row = [
        Paragraph("<b>Работа в сфере IT в Латвии</b>", role_title_style),
        Paragraph("Сентябрь 1995 — Август 2011", period_style),
    ]
    t3 = Table([latvia_row], colWidths=[370, 153])
    t3.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t3)
    story.append(Spacer(1, 5))

    # 3. Образование
    story.append(Paragraph("ОБРАЗОВАНИЕ", section_heading))
    education_items = [
        "<b>Vibe Coding</b> — univerus.ai <i>(обучение продолжается)</i>",
        "<b>AI Agents Developer</b> — AI Institute <i>(обучение продолжается)</i>",
        "<b>AI/ML Developer</b> — AI Institute <i>(обучение продолжается)</i>",
        "<b>Google AI Professional</b> — Coursera <i>(2026)</i>",
        "<b>Level 5 Diploma in Web Application Development</b> — Code Institute <i>(2026)</i>",
        "<b>Postgraduate Diploma in Computer Science with Big Data Analytics</b> — Wrexham Glyndwr University <i>(2023)</i>",
        "<b>BSc (Hons) Computing and IT (Software)</b> — The Open University <i>(2019)</i>",
        "<b>Principles of Warehousing and Storage (NCFE Level 2)</b> — North Warwickshire &amp; Hinckley College <i>(2019)</i>",
        "<b>Team Leading (NCFE Level 2)</b> — North Warwickshire &amp; Hinckley College <i>(2016)</i>",
    ]
    for item in education_items:
        story.append(Paragraph(f"• {item}", bullet_style))
        story.append(Spacer(1, 2))
    story.append(Spacer(1, 4))

    # 4. Повышение квалификации
    story.append(Paragraph("ОБУЧЕНИЕ", section_heading))
    story.append(Paragraph("• <b>Managing projects with PRINCE2</b> (управление проектами по PRINCE2) <i>(2014)</i>", bullet_style))
    story.append(Spacer(1, 5))

    # 5. Сертификаты
    story.append(Paragraph("СЕРТИФИКАТЫ", section_heading))
    certs = [
        "<b>Google AI Professional</b> <i>(2026)</i>",
        "<b>NCFE Level 2 Certificate in Warehousing and Storage</b> <i>(2019)</i>",
        "<b>NCFE Level 2 Certificate in Principles of Team Leading</b> <i>(2016)</i>",
        "<b>PRINCE2 Practitioner</b> <i>(2014)</i>",
    ]
    for c in certs:
        story.append(Paragraph(f"• {c}", bullet_style))
        story.append(Spacer(1, 2))

    # ==========================================
    # PAGE BREAK TO PAGE 2
    # ==========================================
    story.append(PageBreak())

    # Running header page 2
    p2_header_table = Table(
        [
            [
                Paragraph("<b>АНДРИС ЯНЧЕВСКИС</b>", header_style),
                Paragraph("Стр. 2 из 2", ParagraphStyle("RightH2", parent=header_style, alignment=2)),
            ]
        ],
        colWidths=[400, 123],
    )
    p2_header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(p2_header_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("РАБОТА В СФЕРЕ IT В ЛАТВИИ", section_heading))
    story.append(Paragraph("Перечень должностей (IT Jobs Summary):", ParagraphStyle("SubNote", parent=body_style, textColor=colors.HexColor("#475569"))))
    story.append(Spacer(1, 4))

    it_jobs = [
        ("Старший специалист отдела внедрения", "Государственная служба доходов Латвии", "2011 — 2011"),
        ("Бизнес- и системный аналитик", "Государственное агентство социального страхования Латвии", "2009 — 2009"),
        ("Менеджер по продажам решений Business Intelligence", "Data Pro, Латвия", "2006 — 2009"),
        ("Менеджер проектов", "Data Pro, Латвия", "2005 — 2006"),
        ("Системный аналитик", "DIGLAT SIA, Латвия", "2003 — 2005"),
        ("Системный аналитик", "TietoEnator Financial Solutions, Латвия", "1999 — 2002"),
        ("Программист и системный аналитик", "VR Parks SIA, Латвия", "1997 — 1999"),
        ("Поддержка пользователей системы управления запасами", "Lattelekom SIA, Латвия", "1995 — 1997"),
    ]

    for role, org, period in it_jobs:
        job_table = Table(
            [
                [
                    Paragraph(f"• <b>{role}</b> — {org}", bullet_style),
                    Paragraph(period, period_style),
                ]
            ],
            colWidths=[400, 123],
        )
        job_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        story.append(job_table)

    story.append(Spacer(1, 10))

    # 7. Технологии и инструменты
    story.append(Paragraph("ИСПОЛЬЗУЕМЫЕ ПРИЛОЖЕНИЯ, ЯЗЫКИ ПРОГРАММИРОВАНИЯ И ФРЕЙМВОРКИ", section_heading))
    tech_categories = [
        ("Разработка AI-агентов:", "LLM, Embeddings."),
        ("Инструменты AI-разработки:", "Antigravity, Codex, Google AI Studio, Claude Code."),
        ("AI-ассистенты для вопросов и ответов:", "ChatGPT, Gemini, Claude."),
        ("Приложения, языки и фреймворки:", "MS Office (Excel, Word, PowerPoint, Outlook); MS Visio; MS Project; Knapp WMS; Python, PHP, SQL, СУБД (PostgreSQL, Oracle, MySQL), Django, FastAPI, HTML, CSS, JSON, REST API."),
    ]
    for cat, details in tech_categories:
        story.append(Paragraph(f"• <b>{cat}</b> {details}", bullet_style))
        story.append(Spacer(1, 2.5))

    story.append(Spacer(1, 10))

    # 8. Языки
    story.append(Paragraph("ВЛАДЕНИЕ ЯЗЫКАМИ", section_heading))
    languages = [
        ("Латышский", "Родной (Native)"),
        ("Английский", "Хороший (Good)"),
        ("Русский", "Свободный (Fluent)"),
    ]
    for lang, level in languages:
        story.append(Paragraph(f"• <b>{lang}:</b> {level}", bullet_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 10))

    # 9. GitHub
    story.append(Paragraph("GITHUB", section_heading))
    story.append(Paragraph('• <font color="#2563eb"><u>https://github.com/ajandris</u></font>', bullet_style))
    story.append(Spacer(1, 10))

    # 10. Рекомендации
    story.append(Paragraph("РЕКОМЕНДАЦИИ", section_heading))
    story.append(Paragraph("Предоставляются по запросу (References on request).", body_style))

    doc.build(story)
    print(f"Russian CV successfully created at: {output_path}")


if __name__ == "__main__":
    out_october = Path("media/docs/Andris Jancevskis CV October 2026 web RU.pdf")
    out_october.parent.mkdir(parents=True, exist_ok=True)
    build_ru_cv_pdf(out_october)
