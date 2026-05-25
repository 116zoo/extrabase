#!/usr/bin/env python3
"""
pdf_report.py — Generate comprehensive PDF audit report.
Usage:
  python scripts/pdf_report.py --audit runs/.../audit.json --output runs/.../report.pdf
  python scripts/pdf_report.py --audit audit.json --fixes fixes.json --pages pages_audit.json --output report.pdf
Output: JSON status to stdout
"""
import argparse
import json
import os
import sys
import html
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, KeepTogether,
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus.flowables import HRFlowable
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# ── Palette ──────────────────────────────────────────────────────────────────
C_DARK    = colors.HexColor("#0f172a")
C_HEADING = colors.HexColor("#1e293b")
C_SUB     = colors.HexColor("#475569")
C_MUTED   = colors.HexColor("#94a3b8")
C_BORDER  = colors.HexColor("#e2e8f0")
C_BG_ALT  = colors.HexColor("#f8fafc")
C_WHITE   = colors.white

C_P0 = colors.HexColor("#ef4444")
C_P1 = colors.HexColor("#f59e0b")
C_P2 = colors.HexColor("#3b82f6")
C_P3 = colors.HexColor("#94a3b8")
C_OK = colors.HexColor("#22c55e")

C_SCORE_GOOD = colors.HexColor("#dcfce7")
C_SCORE_MED  = colors.HexColor("#fef9c3")
C_SCORE_BAD  = colors.HexColor("#fee2e2")

PAGE_W = A4[0]
MARGIN = 2 * cm


def safe_text(text):
    """Escape HTML special chars for ReportLab Paragraph, preserving allowed tags."""
    if not text:
        return ""
    text = str(text)
    # Replace < and > that are not part of allowed ReportLab tags with HTML entities
    import re
    # Allowed simple tags: b, i, u, br, font, strike, super, sub
    allowed = re.compile(r'<(/?(b|i|u|br|font|strike|super|sub|a)\b[^>]*)>', re.IGNORECASE)
    # Split on potential HTML tags and escape any < > that aren't allowed
    result = []
    pos = 0
    for m in re.finditer(r'<[^>]*>', text):
        before = text[pos:m.start()]
        result.append(html.escape(before, quote=False))
        tag = m.group()
        if allowed.match(tag):
            result.append(tag)
        else:
            result.append(html.escape(tag, quote=False))
        pos = m.end()
    result.append(html.escape(text[pos:], quote=False))
    return "".join(result)


def score_color(score):
    if score is None:
        return C_MUTED
    if score >= 80:
        return C_OK
    if score >= 60:
        return C_P1
    return C_P0


def score_bg(score):
    if score is None:
        return C_BG_ALT
    if score >= 80:
        return C_SCORE_GOOD
    if score >= 60:
        return C_SCORE_MED
    return C_SCORE_BAD


def score_label(score):
    if score is None:
        return "N/A"
    if score >= 80:
        return "✓ Bon"
    if score >= 60:
        return "⚠ Moyen"
    return "✗ Critique"


def priority_color(p):
    return {"P0": C_P0, "P1": C_P1, "P2": C_P2, "P3": C_P3}.get(p, C_MUTED)


# ── Style factory ────────────────────────────────────────────────────────────

def make_styles():
    base = getSampleStyleSheet()
    s = {}

    s["cover_title"] = ParagraphStyle(
        "cover_title", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=28,
        textColor=C_WHITE, leading=34, spaceAfter=6,
    )
    s["cover_sub"] = ParagraphStyle(
        "cover_sub", parent=base["Normal"],
        fontName="Helvetica", fontSize=13,
        textColor=colors.HexColor("#cbd5e1"), leading=18,
    )
    s["h1"] = ParagraphStyle(
        "h1", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=16,
        textColor=C_HEADING, spaceBefore=16, spaceAfter=8, leading=20,
    )
    s["h2"] = ParagraphStyle(
        "h2", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=12,
        textColor=C_HEADING, spaceBefore=10, spaceAfter=5, leading=16,
    )
    s["body"] = ParagraphStyle(
        "body", parent=base["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=C_HEADING, leading=13, spaceAfter=3,
    )
    s["body_muted"] = ParagraphStyle(
        "body_muted", parent=base["Normal"],
        fontName="Helvetica", fontSize=8,
        textColor=C_SUB, leading=12,
    )
    s["bullet"] = ParagraphStyle(
        "bullet", parent=base["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=C_HEADING, leading=13, leftIndent=10, spaceAfter=2,
    )
    s["label"] = ParagraphStyle(
        "label", parent=base["Normal"],
        fontName="Helvetica-Bold", fontSize=8,
        textColor=C_SUB, spaceAfter=2,
    )
    s["center"] = ParagraphStyle(
        "center", parent=base["Normal"],
        fontName="Helvetica", fontSize=9,
        textColor=C_HEADING, alignment=TA_CENTER,
    )
    s["footer"] = ParagraphStyle(
        "footer", parent=base["Normal"],
        fontName="Helvetica", fontSize=7,
        textColor=C_MUTED, alignment=TA_CENTER,
    )
    return s


# ── Cover page ────────────────────────────────────────────────────────────────

def build_cover(story, styles, domain, site_name, date, scores):
    # Dark banner
    banner_data = [[""]]
    banner = Table(banner_data, colWidths=[PAGE_W - 2 * MARGIN], rowHeights=[4.5 * cm])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 24),
        ("LEFTPADDING", (0, 0), (-1, -1), 24),
    ]))

    # Overlay text in banner
    story.append(Table(
        [[Paragraph("Audit SEO · GEO · AEO", styles["cover_title"])],
         [Paragraph(f"{site_name}<br/><font size='11' color='#94a3b8'>{domain}</font>", styles["cover_sub"])],
         [Spacer(1, 0.2 * cm)],
         [Paragraph(f"Rapport généré le {date}", styles["cover_sub"])]],
        colWidths=[PAGE_W - 2 * MARGIN],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), C_DARK),
            ("LEFTPADDING", (0, 0), (-1, -1), 28),
            ("TOPPADDING", (0, 0), (0, 0), 28),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 24),
        ])
    ))
    story.append(Spacer(1, 0.8 * cm))

    # Score cards
    score_rows = [["SEO", scores.get("seo", 0)], ["GEO", scores.get("geo", 0)],
                  ["AEO", scores.get("aeo", 0)], ["Global", scores.get("global", 0)]]
    card_data = []
    card_colors = []
    for label, score in score_rows:
        card_data.append([
            Paragraph(f"<b>{label}</b>", styles["center"]),
            Paragraph(f"<b><font size='18'>{score}</font>/100</b>", styles["center"]),
            Paragraph(score_label(score), styles["center"]),
        ])
        card_colors.append(score_bg(score))

    col_w = (PAGE_W - 2 * MARGIN) / 3
    cards = Table(card_data, colWidths=[col_w, col_w, col_w])
    cmd = [
        ("GRID", (0, 0), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, bg in enumerate(card_colors):
        cmd.append(("BACKGROUND", (1, i), (1, i), bg))
    cards.setStyle(TableStyle(cmd))
    story.append(cards)
    story.append(Spacer(1, 0.5 * cm))


# ── Section helpers ───────────────────────────────────────────────────────────

def section_title(story, styles, text, icon=""):
    story.append(HRFlowable(width="100%", thickness=1, color=C_BORDER, spaceAfter=4))
    story.append(Paragraph(f"{icon} {text}" if icon else text, styles["h1"]))


def sub_title(story, styles, text):
    story.append(Paragraph(text, styles["h2"]))


def kv_table(story, rows, col1=6 * cm, col2=None):
    """Simple 2-col key/value table."""
    if col2 is None:
        col2 = PAGE_W - 2 * MARGIN - col1
    data = []
    for k, v in rows:
        data.append([
            Paragraph(f"<b>{k}</b>", ParagraphStyle("kv_k", fontName="Helvetica-Bold", fontSize=8, textColor=C_SUB)),
            Paragraph(str(v), ParagraphStyle("kv_v", fontName="Helvetica", fontSize=9, textColor=C_HEADING, leading=13)),
        ])
    t = Table(data, colWidths=[col1, col2])
    t.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [C_BG_ALT, C_WHITE]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("LEFTPADDING", (1, 0), (1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.4 * cm))


def issues_table(story, styles, issues, max_rows=20):
    """Table of issues with severity badge."""
    if not issues:
        story.append(Paragraph("Aucun problème détecté.", styles["body_muted"]))
        return
    header = [
        Paragraph("<b>Priorité</b>", styles["center"]),
        Paragraph("<b>Type</b>", styles["center"]),
        Paragraph("<b>Description</b>", styles["center"]),
    ]
    data = [header]
    col_w = PAGE_W - 2 * MARGIN
    for iss in issues[:max_rows]:
        p = iss.get("severity", "P2")
        pc = priority_color(p)
        data.append([
            Paragraph(f'<font color="{pc.hexval()}"><b>{p}</b></font>', styles["center"]),
            Paragraph(iss.get("type", "").replace("_", " "), styles["body"]),
            Paragraph(iss.get("message", ""), styles["body"]),
        ])
    t = Table(data, colWidths=[1.5 * cm, 4 * cm, col_w - 5.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_HEADING),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG_ALT, C_WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    if len(issues) > max_rows:
        story.append(Paragraph(f"... et {len(issues) - max_rows} autres problèmes.", styles["body_muted"]))
    story.append(Spacer(1, 0.4 * cm))


# ── SEO Section ───────────────────────────────────────────────────────────────

def build_seo_section(story, styles, audit):
    seo = audit.get("seo", {})
    if not seo:
        return
    section_title(story, styles, "1. SEO", "")

    score = seo.get("score", 0)
    story.append(Paragraph(
        f'Score SEO : <font color="{score_color(score).hexval()}"><b>{score}/100</b></font> — {score_label(score)}',
        styles["body"]
    ))
    story.append(Spacer(1, 0.3 * cm))

    # On-page
    sub_title(story, styles, "On-page")
    page = seo.get("page", {})
    kv_table(story, [
        ("Title", page.get("title", "—")),
        ("H1", page.get("h1", "—")),
        ("Meta description", (page.get("meta_description") or "—")[:120] + ("..." if len(page.get("meta_description") or "") > 120 else "")),
        ("Nombre de mots", page.get("word_count", "—")),
        ("Canonical", "✓ OK" if page.get("canonical_ok") else "✗ Problème"),
    ])

    # CWV
    sub_title(story, styles, "Core Web Vitals")
    cwv = seo.get("cwv", {})
    mob_cls = cwv.get("mobile_cls", "—")
    desk_cls = cwv.get("desktop_cls", "—")
    kv_table(story, [
        ("PSI Mobile", f"{cwv.get('mobile_score', '—')}/100"),
        ("PSI Desktop", f"{cwv.get('desktop_score', '—')}/100"),
        ("LCP mobile", f"{cwv.get('mobile_lcp_ms', '—')} ms"),
        ("CLS mobile", f"{mob_cls} {'✗ CRITIQUE' if isinstance(mob_cls, float) and mob_cls > 0.1 else '✓'}"),
        ("CLS desktop", f"{desk_cls} {'✗ CRITIQUE' if isinstance(desk_cls, float) and desk_cls > 0.1 else '✓'}"),
        ("TBT mobile", f"{cwv.get('mobile_tbt_ms', '—')} ms"),
    ])

    # Issues
    sub_title(story, styles, "Problèmes CWV")
    cwv_issues = cwv.get("issues", [])
    issues_table(story, styles, cwv_issues)

    # Schema
    sub_title(story, styles, "Schema markup")
    schema = seo.get("schema", {})
    kv_table(story, [
        ("Types présents", ", ".join(schema.get("present", [])) or "Aucun"),
        ("Types manquants", ", ".join(schema.get("missing", [])) or "Aucun"),
        ("Score schema", f"{schema.get('score', 0)}/10"),
    ])

    # Backlinks
    sub_title(story, styles, "Autorité de domaine")
    bl = seo.get("backlinks", {})
    kv_table(story, [
        ("OpenPageRank", f"{bl.get('domain_authority', '—')}/10"),
        ("Rang mondial", bl.get("global_rank", "—")),
        ("Note", bl.get("notes", "—")),
    ])

    # SERP
    sub_title(story, styles, "Visibilité SERP")
    serp = seo.get("serp_visibility", {})
    kv_table(story, [
        ("Mot-clé principal", serp.get("keyword", "—")),
        ("Dans le top 10", "✓ Oui" if serp.get("target_in_top10") else "✗ Non"),
        ("Observation", serp.get("observation", "—")),
    ])


# ── GEO Section ───────────────────────────────────────────────────────────────

def build_geo_section(story, styles, audit):
    geo = audit.get("geo", {})
    if not geo:
        return
    story.append(PageBreak())
    section_title(story, styles, "2. GEO — AI Search Optimization", "")

    score = geo.get("score", 0)
    story.append(Paragraph(
        f'Score GEO : <font color="{score_color(score).hexval()}"><b>{score}/100</b></font> — {score_label(score)}',
        styles["body"]
    ))
    story.append(Spacer(1, 0.3 * cm))

    # AI crawler access
    sub_title(story, styles, "Accès bots IA")
    ai = geo.get("ai_crawler_access", {})
    kv_table(story, [
        ("Bots IA bloqués", ", ".join(ai.get("robots_ai_blocked", [])) or "Aucun — ✓"),
        ("Score", f"{ai.get('score', 0)}/{ai.get('max', 25)}"),
    ])

    # llms.txt
    sub_title(story, styles, "llms.txt")
    llms = geo.get("llms_txt", {})
    issues_llms = llms.get("issues", [])
    kv_table(story, [
        ("Présent", "✓ Oui" if llms.get("exists") else "✗ Non"),
        ("Encodage UTF-8", "✗ Corrompu" if llms.get("encoding_issue") else "✓ OK"),
        ("Score", f"{llms.get('score', 0)}/{llms.get('max', 25)}"),
    ])
    if issues_llms:
        for iss in issues_llms:
            story.append(Paragraph(f"• {iss}", styles["bullet"]))
        story.append(Spacer(1, 0.3 * cm))

    # Entity schema
    sub_title(story, styles, "Schema entité")
    ent = geo.get("entity_schema", {})
    kv_table(story, [
        ("LocalBusiness", "✓" if ent.get("has_local_business") else "✗ Manquant"),
        ("Person", "✓" if ent.get("has_person_schema") else "✗ Manquant"),
        ("MedicalBusiness", "✓" if ent.get("has_medical_business") else "✗ Manquant"),
        ("Score", f"{ent.get('score', 0)}/{ent.get('max', 25)}"),
    ])

    # Citability
    sub_title(story, styles, "Citabilité")
    cit = geo.get("citability", {})
    kv_table(story, [
        ("Section FAQ", "✓" if cit.get("has_faq_section") else "✗"),
        ("Descriptions services claires", "✓" if cit.get("clear_service_descriptions") else "✗"),
        ("Auteur identifié", "✓" if cit.get("author_identified") else "✗"),
        ("Credentials visibles", "✓" if cit.get("author_credentials_visible") else "✗"),
        ("Score", f"{cit.get('score', 0)}/{cit.get('max', 10)}"),
    ])


# ── AEO Section ───────────────────────────────────────────────────────────────

def build_aeo_section(story, styles, audit):
    aeo = audit.get("aeo", {})
    if not aeo:
        return
    story.append(PageBreak())
    section_title(story, styles, "3. AEO — Answer Engine Optimization", "")

    score = aeo.get("score", 0)
    story.append(Paragraph(
        f'Score AEO : <font color="{score_color(score).hexval()}"><b>{score}/100</b></font> — {score_label(score)}',
        styles["body"]
    ))
    story.append(Spacer(1, 0.3 * cm))

    sections = [
        ("Découvrabilité (FAQ, schema)", "discovery"),
        ("Structure contenu", "content_structure"),
        ("Token economics", "token_economics"),
        ("Capability signaling", "capability_signaling"),
        ("UX bridge (CTA, contact)", "ux_bridge"),
    ]
    rows = []
    for label, key in sections:
        sec = aeo.get(key, {})
        s = sec.get("score", "—")
        m = sec.get("max", "—")
        issues = "; ".join(sec.get("issues", []))[:80] if sec.get("issues") else "✓"
        rows.append((label, f"{s}/{m}", issues))

    data = [[Paragraph("<b>Section</b>", styles["center"]),
             Paragraph("<b>Score</b>", styles["center"]),
             Paragraph("<b>Note</b>", styles["center"])]]
    col_w = PAGE_W - 2 * MARGIN
    for label, score_str, note in rows:
        data.append([
            Paragraph(label, styles["body"]),
            Paragraph(score_str, styles["center"]),
            Paragraph(note, styles["body"]),
        ])
    t = Table(data, colWidths=[5 * cm, 2.5 * cm, col_w - 7.5 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_HEADING),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG_ALT, C_WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))


# ── Pages Section ─────────────────────────────────────────────────────────────

def build_pages_section(story, styles, pages_data):
    if not pages_data:
        return
    story.append(PageBreak())
    section_title(story, styles, "4. Audit toutes les pages", "")

    agg = pages_data.get("aggregate", {})
    total = agg.get("total_pages", 0)

    # Summary stats
    kv_table(story, [
        ("Pages analysées", f"{total}"),
        ("Pages OK (200)", f"{agg.get('pages_ok', 0)}"),
        ("Erreurs 4xx/5xx", f"{agg.get('pages_4xx_5xx', 0)}"),
        ("Redirections", f"{agg.get('pages_redirect', 0)}"),
        ("Sans title", f"{agg.get('pages_missing_title', 0)}"),
        ("Sans H1", f"{agg.get('pages_missing_h1', 0)}"),
        ("Sans meta description", f"{agg.get('pages_missing_meta_desc', 0)}"),
        ("Sans schema", f"{agg.get('pages_missing_schema', 0)}"),
        ("Contenu mince (<300 mots)", f"{agg.get('pages_thin_content', 0)}"),
        ("Titles en doublon", f"{agg.get('duplicate_titles_count', 0)} groupe(s)"),
        ("Metas en doublon", f"{agg.get('duplicate_metas_count', 0)} groupe(s)"),
    ], col1=5.5 * cm)

    # Issues summary
    sub_title(story, styles, "Distribution des problèmes")
    p0 = agg.get("p0_issues", 0)
    p1 = agg.get("p1_issues", 0)
    p2 = agg.get("p2_issues", 0)
    data = [[
        Paragraph(f'<font color="{C_P0.hexval()}"><b>P0 Critique</b></font>', styles["center"]),
        Paragraph(f'<font color="{C_P1.hexval()}"><b>P1 Important</b></font>', styles["center"]),
        Paragraph(f'<font color="{C_P2.hexval()}"><b>P2 Moyen</b></font>', styles["center"]),
    ], [
        Paragraph(f"<b>{p0}</b>", styles["center"]),
        Paragraph(f"<b>{p1}</b>", styles["center"]),
        Paragraph(f"<b>{p2}</b>", styles["center"]),
    ]]
    col_w = (PAGE_W - 2 * MARGIN) / 3
    t = Table(data, colWidths=[col_w, col_w, col_w])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 0), (0, 0), C_SCORE_BAD),
        ("BACKGROUND", (1, 0), (1, 0), C_SCORE_MED),
        ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#dbeafe")),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # Duplicate titles
    dup_titles = agg.get("duplicate_titles", {})
    if dup_titles:
        sub_title(story, styles, "Titles en doublon")
        for title, urls in list(dup_titles.items())[:8]:
            story.append(Paragraph(f'<b>"{title[:60]}"</b>', styles["body"]))
            for u in urls[:4]:
                story.append(Paragraph(f"  → {u}", styles["body_muted"]))
            story.append(Spacer(1, 0.15 * cm))

    # Top pages with issues
    sub_title(story, styles, "Pages les plus problématiques (top 15)")
    all_pages = pages_data.get("pages", [])
    pages_with_issues = [p for p in all_pages if p.get("issues")]
    pages_with_issues.sort(key=lambda x: (
        -sum(1 for i in x["issues"] if i["severity"] == "P0"),
        -sum(1 for i in x["issues"] if i["severity"] == "P1"),
        -len(x["issues"]),
    ))

    header = [
        Paragraph("<b>URL</b>", styles["center"]),
        Paragraph("<b>P0</b>", styles["center"]),
        Paragraph("<b>P1</b>", styles["center"]),
        Paragraph("<b>P2</b>", styles["center"]),
        Paragraph("<b>Problèmes principaux</b>", styles["center"]),
    ]
    data = [header]
    col_w = PAGE_W - 2 * MARGIN
    for page in pages_with_issues[:15]:
        url = page["url"].replace("https://", "").replace("http://", "")
        if len(url) > 45:
            url = url[:42] + "..."
        p0 = sum(1 for i in page["issues"] if i["severity"] == "P0")
        p1 = sum(1 for i in page["issues"] if i["severity"] == "P1")
        p2 = sum(1 for i in page["issues"] if i["severity"] == "P2")
        issue_types = list({i["type"].replace("_", " ") for i in page["issues"]})[:3]
        data.append([
            Paragraph(url, styles["body_muted"]),
            Paragraph(f'<font color="{C_P0.hexval()}"><b>{p0}</b></font>' if p0 else "0", styles["center"]),
            Paragraph(f'<font color="{C_P1.hexval()}"><b>{p1}</b></font>' if p1 else "0", styles["center"]),
            Paragraph(f'<font color="{C_P2.hexval()}"><b>{p2}</b></font>' if p2 else "0", styles["center"]),
            Paragraph(", ".join(issue_types), styles["body_muted"]),
        ])

    t = Table(data, colWidths=[5.5 * cm, 1.2 * cm, 1.2 * cm, 1.2 * cm, col_w - 9.1 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_HEADING),
        ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG_ALT, C_WHITE]),
        ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (1, 0), (3, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    # PSI results if available
    psi_pages = [p for p in all_pages if p.get("psi_mobile") and p["psi_mobile"].get("score") is not None]
    if psi_pages:
        sub_title(story, styles, "PageSpeed Insights (pages testées)")
        header_psi = [
            Paragraph("<b>URL</b>", styles["center"]),
            Paragraph("<b>PSI Mobile</b>", styles["center"]),
            Paragraph("<b>LCP</b>", styles["center"]),
            Paragraph("<b>CLS</b>", styles["center"]),
        ]
        data_psi = [header_psi]
        for page in psi_pages[:10]:
            url = page["url"].replace("https://", "").replace("http://", "")
            if len(url) > 50:
                url = url[:47] + "..."
            psi = page["psi_mobile"]
            sc = psi.get("score")
            lcp = psi.get("lcp_ms")
            cls = psi.get("cls")
            sc_color = score_color(sc).hexval()
            cls_flag = "✗" if (cls and cls > 0.1) else "✓"
            lcp_flag = "✗" if (lcp and lcp > 2500) else "✓"
            data_psi.append([
                Paragraph(url, styles["body_muted"]),
                Paragraph(f'<font color="{sc_color}"><b>{sc}/100</b></font>', styles["center"]),
                Paragraph(f"{lcp} ms {lcp_flag}" if lcp else "—", styles["center"]),
                Paragraph(f"{cls} {cls_flag}" if cls is not None else "—", styles["center"]),
            ])
        col_w = PAGE_W - 2 * MARGIN
        t = Table(data_psi, colWidths=[6 * cm, 3 * cm, 3 * cm, col_w - 12 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_HEADING),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG_ALT, C_WHITE]),
            ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))


# ── Competitors Section ───────────────────────────────────────────────────────

def build_competitors_section(story, styles, audit):
    comp = audit.get("competitors", {})
    detected = comp.get("detected", [])
    gap = comp.get("gap_analysis", {})
    if not detected and not gap:
        return
    story.append(PageBreak())
    section_title(story, styles, "5. Analyse concurrents", "")

    if detected:
        sub_title(story, styles, "Concurrents détectés")
        header = [
            Paragraph("<b>Domaine</b>", styles["center"]),
            Paragraph("<b>Type</b>", styles["center"]),
            Paragraph("<b>Score est.</b>", styles["center"]),
            Paragraph("<b>Schema</b>", styles["center"]),
            Paragraph("<b>llms.txt</b>", styles["center"]),
        ]
        data = [header]
        col_w = PAGE_W - 2 * MARGIN
        for c in detected:
            sc = c.get("score_estimate", "—")
            data.append([
                Paragraph(c.get("domain", "—"), styles["body"]),
                Paragraph(c.get("type", "—"), styles["body_muted"]),
                Paragraph(f"{sc}/100" if sc != "—" else "—", styles["center"]),
                Paragraph("✓" if c.get("has_schema") else "✗", styles["center"]),
                Paragraph("✓" if c.get("has_llms_txt") else "✗", styles["center"]),
            ])
        t = Table(data, colWidths=[4.5 * cm, 3.5 * cm, 2.5 * cm, 2 * cm, col_w - 12.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_HEADING),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG_ALT, C_WHITE]),
            ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.4 * cm))

    if gap:
        sub_title(story, styles, "Analyse des écarts")
        for key, val in gap.items():
            story.append(Paragraph(f"• <b>{key.replace('_', ' ').title()} :</b> {val}", styles["bullet"]))
        story.append(Spacer(1, 0.3 * cm))


# ── Fixes Section ─────────────────────────────────────────────────────────────

def build_fixes_section(story, styles, fixes_data):
    # fixes_data can be a list or a dict with "fixes" key
    if isinstance(fixes_data, list):
        fixes = fixes_data
        by_p = {}
        for f in fixes:
            p = f.get("priority", "unknown")
            by_p[p] = by_p.get(p, 0) + 1
        applied_count = sum(1 for f in fixes if f.get("status") == "applied")
        summary = {p: count for p, count in by_p.items()}
        summary["total"] = len(fixes)
        summary["applied"] = applied_count
    else:
        fixes = fixes_data.get("fixes", [])
        summary = fixes_data.get("summary", {})
        applied_count = summary.get("applied", sum(1 for f in fixes if f.get("status") == "applied"))
    if not fixes:
        return
    story.append(PageBreak())
    section_title(story, styles, "6. Plan d'action prioritaire", "")

    sub_title(story, styles, "Résumé")
    kv_table(story, [
        ("P0 Critique", f"{summary.get('P0', 0)} fix(es)"),
        ("P1 Important", f"{summary.get('P1', 0)} fix(es)"),
        ("P2 Moyen terme", f"{summary.get('P2', 0)} fix(es)"),
        ("Appliqués", f"{summary.get('applied', applied_count)}/{summary.get('total', len(fixes))} correctifs"),
        ("Total", f"{summary.get('total', len(fixes))} correctifs"),
    ], col1=4 * cm)

    for priority in ["P0", "P1", "P2", "P3"]:
        prio_fixes = [f for f in fixes if f.get("priority") == priority]
        if not prio_fixes:
            continue
        pc = priority_color(priority)
        story.append(Paragraph(
            f'<font color="{pc.hexval()}"><b>▌ {priority}</b></font> — {len(prio_fixes)} correctif(s)',
            styles["h2"]
        ))
        header = [
            Paragraph("<b>#</b>", styles["center"]),
            Paragraph("<b>Titre</b>", styles["center"]),
            Paragraph("<b>Pilier</b>", styles["center"]),
            Paragraph("<b>Effort</b>", styles["center"]),
            Paragraph("<b>Impact estimé</b>", styles["center"]),
            Paragraph("<b>Appliqué</b>", styles["center"]),
        ]
        data = [header]
        col_w = PAGE_W - 2 * MARGIN
        for fix in prio_fixes:
            is_applied = fix.get("applied") or fix.get("status") == "applied"
            applied = "✓" if is_applied else "—"
            title_text = safe_text(fix.get("title", fix.get("fix", fix.get("description", ""))))
            impact_text = safe_text(str(fix.get("estimated_impact", fix.get("impact", "")))[:60])
            pillar_text = safe_text(fix.get("pillar", fix.get("category", "")))
            effort_text = safe_text(fix.get("effort", ""))
            data.append([
                Paragraph(safe_text(fix.get("id", "")), styles["body_muted"]),
                Paragraph(title_text, styles["body"]),
                Paragraph(pillar_text, styles["body_muted"]),
                Paragraph(effort_text, styles["body_muted"]),
                Paragraph(impact_text, styles["body_muted"]),
                Paragraph(f'<font color="{C_OK.hexval()}">{applied}</font>' if is_applied else applied,
                          styles["center"]),
            ])
        t = Table(data, colWidths=[1.8 * cm, 5 * cm, 2 * cm, 1.8 * cm, col_w - 12.1 * cm, 1.5 * cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_HEADING),
            ("TEXTCOLOR", (0, 0), (-1, 0), C_WHITE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_BG_ALT, C_WHITE]),
            ("GRID", (0, 0), (-1, -1), 0.3, C_BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("ALIGN", (5, 0), (5, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))


# ── Main generator ────────────────────────────────────────────────────────────

def generate_pdf(audit_data: dict, output_path: str,
                 fixes_data: dict = None, pages_data: dict = None) -> dict:
    if not HAS_REPORTLAB:
        return {"success": False, "error": "reportlab not installed. Run: pip install reportlab"}

    domain = audit_data.get("domain", "unknown")
    site_name = audit_data.get("url", domain)
    date = audit_data.get("date", datetime.today().strftime("%Y-%m-%d"))
    raw_scores = audit_data.get("scores", {})
    # Normalise scores: each value may be a plain int or a dict {"score": N, ...}
    scores = {}
    for k, v in raw_scores.items():
        if isinstance(v, dict):
            scores[k] = v.get("score", 0)
        else:
            scores[k] = v

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=MARGIN, bottomMargin=MARGIN,
        leftMargin=MARGIN, rightMargin=MARGIN,
        title=f"Audit SEO GEO AEO — {domain}",
        author="SEO-GEO-AEO Skill",
    )
    styles = make_styles()
    story = []

    # Cover
    build_cover(story, styles, domain, site_name, date, scores)
    story.append(PageBreak())

    # SEO
    build_seo_section(story, styles, audit_data)

    # GEO
    build_geo_section(story, styles, audit_data)

    # AEO
    build_aeo_section(story, styles, audit_data)

    # Pages
    if pages_data:
        build_pages_section(story, styles, pages_data)

    # Competitors
    build_competitors_section(story, styles, audit_data)

    # Fixes
    if fixes_data:
        build_fixes_section(story, styles, fixes_data)

    # Footer on last page
    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER))
    story.append(Paragraph(
        f"Rapport généré par SEO-GEO-AEO Skill v1.0 — {date} — {domain}",
        styles["footer"]
    ))

    doc.build(story)
    return {
        "success": True,
        "path": output_path,
        "domain": domain,
        "date": date,
        "pages": pages_data.get("aggregate", {}).get("total_pages") if pages_data else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate comprehensive PDF audit report")
    parser.add_argument("--audit",  required=True, help="Path to audit.json")
    parser.add_argument("--fixes",  help="Path to fixes.json (optional)")
    parser.add_argument("--pages",  help="Path to pages_audit.json (optional)")
    parser.add_argument("--output", required=True, help="Output PDF path")
    args = parser.parse_args()

    with open(args.audit) as f:
        audit_data = json.load(f)

    fixes_data = None
    if args.fixes and os.path.exists(args.fixes):
        with open(args.fixes) as f:
            fixes_data = json.load(f)

    pages_data = None
    if args.pages and os.path.exists(args.pages):
        with open(args.pages) as f:
            pages_data = json.load(f)

    result = generate_pdf(audit_data, args.output, fixes_data, pages_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
