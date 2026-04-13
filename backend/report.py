"""
PDF report generator using ReportLab.
Produces a per-dataset quality report.
"""

from __future__ import annotations
import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF

from quality.scorer import QualityReport

SCORE_COLORS = {
    "A": colors.HexColor("#22c55e"),
    "B": colors.HexColor("#84cc16"),
    "C": colors.HexColor("#f59e0b"),
    "D": colors.HexColor("#f97316"),
    "F": colors.HexColor("#ef4444"),
}

DIMENSION_LABELS = {
    "completeness":     "Completeness",
    "freshness":        "Freshness",
    "consistency":      "Consistency",
    "uniqueness":       "Uniqueness",
    "validity":         "Validity",
    "accessibility":    "Accessibility",
    "metadata_quality": "Metadata Quality",
}


def _score_bar(score: float, width: float = 200, height: float = 14) -> Drawing:
    d = Drawing(width, height)
    # Background
    d.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#e5e7eb"), strokeColor=None))
    # Fill
    fill_w = max(2, width * score / 100)
    fill_color = colors.HexColor("#22c55e") if score >= 80 else (
        colors.HexColor("#f59e0b") if score >= 60 else colors.HexColor("#ef4444")
    )
    d.add(Rect(0, 0, fill_w, height, fillColor=fill_color, strokeColor=None))
    # Score text
    d.add(String(width / 2, 2, f"{score:.0f}", fontSize=9, textAnchor="middle",
                 fillColor=colors.black))
    return d


def generate_pdf_report(report: QualityReport) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title2", parent=styles["Title"], fontSize=18, spaceAfter=6
    )
    heading_style = ParagraphStyle(
        "Heading2", parent=styles["Heading2"], spaceBefore=12, spaceAfter=4
    )
    normal = styles["Normal"]
    small = ParagraphStyle("Small", parent=normal, fontSize=9, textColor=colors.HexColor("#6b7280"))

    story = []

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph("Data Quality Report", title_style))
    story.append(Paragraph(f"<b>{report.dataset_title or report.dataset_id}</b>", styles["Heading1"]))
    story.append(Paragraph(f"Organization: {report.organization}", normal))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} | "
        f"Audited: {report.audited_at or 'N/A'}",
        small
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Spacer(1, 0.3 * cm))

    # ── Overall Score ─────────────────────────────────────────────────────
    grade_color = SCORE_COLORS.get(report.grade, colors.gray)
    overall_data = [[
        Paragraph("<b>Overall Score</b>", styles["Heading2"]),
        Paragraph(
            f'<font size="36" color="{grade_color.hexval() if hasattr(grade_color, "hexval") else "#000"}">'
            f'<b>{report.overall_score:.1f}</b></font>',
            normal
        ),
        Paragraph(f'Grade: <b>{report.grade}</b>', styles["Heading2"]),
    ]]
    t = Table(overall_data, colWidths=[6 * cm, 6 * cm, 5 * cm])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f9fafb")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#e5e7eb")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # ── ML Insights ───────────────────────────────────────────────────────
    if report.ml_topic or report.ml_abandoned_probability is not None:
        story.append(Paragraph("AI Insights", heading_style))
        if report.ml_topic:
            story.append(Paragraph(f"<b>Detected Topic:</b> {report.ml_topic}", normal))
        if report.ml_abandoned_probability is not None:
            ab_pct = report.ml_abandoned_probability * 100
            ab_label = "High risk" if ab_pct > 70 else ("Medium risk" if ab_pct > 40 else "Low risk")
            story.append(Paragraph(
                f"<b>Abandonment Risk:</b> {ab_pct:.0f}% ({ab_label})", normal
            ))
        story.append(Spacer(1, 0.3 * cm))

    # ── Dimension Scores ──────────────────────────────────────────────────
    story.append(Paragraph("Quality Dimension Scores", heading_style))

    dim_data = [["Dimension", "Score", "Bar"]]
    for key, label in DIMENSION_LABELS.items():
        score = report.dimension_scores.get(key, 0.0)
        dim_data.append([
            label,
            f"{score:.1f}/100",
            _score_bar(score),
        ])

    t2 = Table(dim_data, colWidths=[5 * cm, 3 * cm, 9 * cm])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.5 * cm))

    # ── Issues ────────────────────────────────────────────────────────────
    if report.all_issues:
        story.append(Paragraph("Issues Found", heading_style))
        for issue in report.all_issues:
            story.append(Paragraph(f"• {issue}", normal))
        story.append(Spacer(1, 0.3 * cm))

    # ── Footer ────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    story.append(Paragraph(
        "Generated by DataChecker — Saudi Open Data Quality Audit Tool",
        small
    ))

    doc.build(story)
    return buf.getvalue()
