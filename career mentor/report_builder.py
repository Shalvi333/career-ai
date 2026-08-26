"""PDF builder for the downloadable Career AI student report."""

from __future__ import annotations

from html import escape
from io import BytesIO
import re
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PURPLE = colors.HexColor("#5B35D5")
INK = colors.HexColor("#28184D")
MUTED = colors.HexColor("#6F6288")
PINK = colors.HexColor("#EF5A87")
MINT = colors.HexColor("#12A88D")
PALE = colors.HexColor("#F5F1FF")
LINE = colors.HexColor("#DED4F5")


def _text(value: Any) -> str:
    """Make user text safe for ReportLab paragraphs and PDF fonts."""
    cleaned = str(value or "")
    cleaned = cleaned.replace("\u2013", "-").replace("\u2014", "-")
    cleaned = cleaned.replace("\u2018", "'").replace("\u2019", "'")
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"')
    cleaned = cleaned.replace("\u2022", "-").replace("\u2713", "Completed")
    cleaned = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]", "", cleaned)
    return escape(cleaned).replace("\n", "<br/>")


def _page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 8.5 * mm, "Career AI - Student Career Exploration Report")
    canvas.drawRightString(A4[0] - 18 * mm, 8.5 * mm, f"Page {document.page}")
    canvas.restoreState()


def build_career_report(data: dict[str, Any]) -> bytes:
    """Return a polished A4 career report as PDF bytes."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=18 * mm,
        title=f"Career AI report for {data.get('student_name', 'Student')}",
        author="Career AI",
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=INK, alignment=TA_CENTER, spaceAfter=6),
        "subtitle": ParagraphStyle("ReportSubtitle", parent=base["Normal"], fontSize=10, leading=14, textColor=MUTED, alignment=TA_CENTER, spaceAfter=16),
        "h1": ParagraphStyle("Section", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=PURPLE, spaceBefore=10, spaceAfter=7),
        "h2": ParagraphStyle("SmallHeading", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=INK, spaceBefore=4, spaceAfter=3),
        "body": ParagraphStyle("Body", parent=base["BodyText"], fontSize=9.2, leading=13.5, textColor=INK, spaceAfter=5),
        "muted": ParagraphStyle("Muted", parent=base["BodyText"], fontSize=8.2, leading=12, textColor=MUTED, spaceAfter=4),
        "tiny": ParagraphStyle("Tiny", parent=base["BodyText"], fontSize=7.4, leading=10, textColor=MUTED),
    }
    story: list[Any] = []
    student_name = _text(data.get("student_name") or "Student")
    generated = _text(data.get("generated_on") or "")
    story.extend([
        Paragraph("CAREER AI", styles["subtitle"]),
        Paragraph(f"Career Exploration Report for {student_name}", styles["title"]),
        Paragraph(f"Generated {generated} | A personalised exploration summary", styles["subtitle"]),
    ])

    profile_rows = [
        [Paragraph("Career quiz", styles["h2"]), Paragraph(_text(data.get("career_quiz_status", "Not completed")), styles["body"])],
        [Paragraph("RIASEC quiz", styles["h2"]), Paragraph(_text(data.get("riasec_status", "Not completed")), styles["body"])],
        [Paragraph("Current direction", styles["h2"]), Paragraph(_text(data.get("current_direction", "Complete a quiz to unlock this section.")), styles["body"])],
    ]
    profile_table = Table(profile_rows, colWidths=[42 * mm, 126 * mm], hAlign="LEFT")
    profile_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), .6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), .35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([profile_table, Spacer(1, 9)])

    answers = data.get("profile_answers") or []
    if answers:
        story.append(Paragraph("Profile signals used", styles["h1"]))
        for label, answer in answers[:10]:
            story.append(KeepTogether([
                Paragraph(_text(label), styles["h2"]),
                Paragraph(_text(answer), styles["body"]),
            ]))

    matches = data.get("career_matches") or []
    story.append(Paragraph("Top career matches", styles["h1"]))
    if matches:
        match_rows = [[Paragraph("Career", styles["h2"]), Paragraph("Match", styles["h2"]), Paragraph("Why it may suit you", styles["h2"])]]
        for match in matches[:6]:
            match_rows.append([
                Paragraph(_text(match.get("career")), styles["body"]),
                Paragraph(_text(match.get("score")), styles["body"]),
                Paragraph(_text(match.get("reason")), styles["body"]),
            ])
        match_table = Table(match_rows, colWidths=[42 * mm, 19 * mm, 107 * mm], repeatRows=1)
        match_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PURPLE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
            ("BOX", (0, 0), (-1, -1), .6, LINE),
            ("INNERGRID", (0, 0), (-1, -1), .35, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(match_table)
    else:
        story.append(Paragraph("No career match is shown until at least one quiz is completed.", styles["body"]))

    riasec = data.get("riasec_scores") or []
    if riasec:
        story.extend([Spacer(1, 4), Paragraph("RIASEC profile", styles["h1"])])
        riasec_rows = [[Paragraph(_text(name), styles["h2"]), Paragraph(_text(score), styles["body"])] for name, score in riasec]
        riasec_table = Table(riasec_rows, colWidths=[84 * mm, 84 * mm])
        riasec_table.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [PALE, colors.white]),
            ("BOX", (0, 0), (-1, -1), .5, LINE),
            ("INNERGRID", (0, 0), (-1, -1), .3, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(riasec_table)

    story.append(PageBreak())
    story.append(Paragraph("Education and funding routes", styles["h1"]))
    universities = data.get("universities") or []
    if universities:
        story.append(Paragraph("Universities to research", styles["h2"]))
        university_rows = [[Paragraph("Institution", styles["h2"]), Paragraph("Country / field", styles["h2"]), Paragraph("Why it appears", styles["h2"])]]
        for item in universities[:6]:
            university_rows.append([
                Paragraph(_text(item.get("name")), styles["body"]),
                Paragraph(_text(" - ".join(part for part in (item.get("country"), item.get("field")) if part)), styles["body"]),
                Paragraph(_text(item.get("description") or item.get("aid") or "Verify the course and entry requirements on the official website."), styles["body"]),
            ])
        table = Table(university_rows, colWidths=[55 * mm, 45 * mm, 68 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PURPLE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
            ("BOX", (0, 0), (-1, -1), .5, LINE), ("INNERGRID", (0, 0), (-1, -1), .3, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("Complete a quiz to unlock focused university directions.", styles["body"]))

    scholarships = data.get("scholarships") or []
    story.extend([Spacer(1, 7), Paragraph("Scholarships to verify", styles["h2"])])
    if scholarships:
        scholarship_rows = [[Paragraph("Scholarship", styles["h2"]), Paragraph("Coverage", styles["h2"]), Paragraph("Best for", styles["h2"])]]
        for item in scholarships[:6]:
            scholarship_rows.append([
                Paragraph(_text(item.get("name")), styles["body"]),
                Paragraph(_text(item.get("coverage")), styles["body"]),
                Paragraph(_text(item.get("best_for")), styles["body"]),
            ])
        table = Table(scholarship_rows, colWidths=[55 * mm, 53 * mm, 60 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PINK), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
            ("BOX", (0, 0), (-1, -1), .5, LINE), ("INNERGRID", (0, 0), (-1, -1), .3, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
    else:
        story.append(Paragraph("No focused scholarship suggestions are available yet.", styles["body"]))

    story.extend([Spacer(1, 8), Paragraph("Learning roadmap", styles["h1"])])
    roadmap = data.get("roadmap") or []
    if roadmap:
        roadmap_rows = []
        for index, step in enumerate(roadmap, 1):
            status = "Completed" if step.get("completed") else "Next"
            roadmap_rows.append([
                Paragraph(str(index), styles["h2"]),
                Paragraph(_text(step.get("title")), styles["h2"]),
                Paragraph(_text(status), styles["body"]),
                Paragraph(_text(step.get("description")), styles["body"]),
            ])
        table = Table(roadmap_rows, colWidths=[10 * mm, 51 * mm, 20 * mm, 87 * mm])
        table.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [PALE, colors.white]),
            ("BOX", (0, 0), (-1, -1), .5, LINE), ("INNERGRID", (0, 0), (-1, -1), .3, LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5), ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)

    weekly = data.get("weekly_goals") or []
    if weekly:
        story.extend([Spacer(1, 7), Paragraph("Weekly action plan", styles["h1"])])
        for goal in weekly[:8]:
            status = "Completed" if goal.get("completed") else f"Due {goal.get('due_date', 'not set')}"
            story.append(Paragraph(f"<b>{_text(goal.get('title'))}</b> - {_text(status)}", styles["body"]))
            if goal.get("notes"):
                story.append(Paragraph(_text(goal.get("notes")), styles["muted"]))

    story.extend([
        Spacer(1, 12),
        Paragraph("Important note", styles["h1"]),
        Paragraph(
            "This student project supports career exploration; it is not professional career counselling. "
            "Career matches are starting points, not guarantees. Always verify admissions, fees, rankings, "
            "scholarship eligibility, deadlines, and professional licensing on official sources, and discuss "
            "important decisions with a qualified counsellor, teacher, or guardian.",
            styles["muted"],
        ),
    ])
    document.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    return buffer.getvalue()
