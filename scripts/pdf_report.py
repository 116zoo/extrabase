#!/usr/bin/env python3
"""
pdf_report.py — Generate PDF audit report from audit.json data.
Usage: python scripts/pdf_report.py --audit runs/example.fr/2026-05-24/audit.json --output runs/example.fr/2026-05-24/report.pdf
Output: JSON status to stdout
"""
import argparse
import json
import os
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.enums import TA_CENTER
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def generate_pdf(audit_data: dict, output_path: str) -> dict:
    if not HAS_REPORTLAB:
        return {"success": False, "error": "reportlab not installed. Run: pip install reportlab"}

    domain = audit_data.get("domain", "unknown")
    date = audit_data.get("date", datetime.today().strftime("%Y-%m-%d"))
    scores = audit_data.get("scores", {})
    fixes = audit_data.get("fixes", {})

    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=22, textColor=colors.HexColor("#1e293b"), spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "CustomSub", parent=styles["Normal"],
        fontSize=11, textColor=colors.HexColor("#64748b"), spaceAfter=20
    )
    story.append(Paragraph("Audit SEO \u00b7 GEO \u00b7 AEO", title_style))
    story.append(Paragraph(f"{domain} \u2014 {date}", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    story.append(Spacer(1, 0.5*cm))

    # Scores table
    score_data = [["Pilier", "Score", "Statut"]]
    for pillar, label in [("seo", "SEO"), ("geo", "GEO"), ("aeo", "AEO"), ("global", "Global")]:
        score = scores.get(pillar, 0) or 0
        if score >= 80:
            status = "\u2713 Bon"
        elif score >= 60:
            status = "\u26a0 Moyen"
        else:
            status = "\u2717 Critique"
        score_data.append([label, f"{score}/100", status])

    score_table = Table(score_data, colWidths=[5*cm, 4*cm, 5*cm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 11),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("FONTSIZE", (0, 1), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.8*cm))

    # Fixes summary
    h2_style = ParagraphStyle(
        "H2Custom", parent=styles["Heading2"],
        fontSize=14, textColor=colors.HexColor("#1e293b"), spaceAfter=8
    )
    story.append(Paragraph("Correctifs prioritaires", h2_style))

    priority_colors = {"P0": "#ef4444", "P1": "#f59e0b", "P2": "#3b82f6", "P3": "#94a3b8"}
    for priority in ["P0", "P1", "P2", "P3"]:
        fix_list = fixes.get(priority, [])
        if not fix_list:
            continue
        hex_color = priority_colors[priority]
        story.append(Paragraph(
            f'<font color="{hex_color}"><b>{priority}</b></font> \u2014 {len(fix_list)} correctif(s)',
            styles["Normal"]
        ))
        for fix in fix_list[:10]:
            story.append(Paragraph(
                f"  \u2022 {fix.get('title', 'Fix')} [{fix.get('category', '')}]",
                styles["Normal"]
            ))
        story.append(Spacer(1, 0.3*cm))

    doc.build(story)
    return {"success": True, "path": output_path, "domain": domain, "date": date}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", required=True, help="Path to audit.json")
    parser.add_argument("--output", required=True, help="Output PDF path")
    args = parser.parse_args()

    with open(args.audit) as f:
        audit_data = json.load(f)

    result = generate_pdf(audit_data, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
