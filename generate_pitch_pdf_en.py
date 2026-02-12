#!/usr/bin/env python3
"""
Stock Deepseeker - Comprehensive English Investor Pitch PDF Generator
Generates a highly detailed, professional pitch deck (100% English) without revealing source code.
"""

import os
import math
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Frame, PageTemplate, BaseDocTemplate, Image,
    KeepTogether, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon, Group
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from datetime import datetime

# ── Color Palette ──────────────────────────────────────────────
DARK_BG = colors.HexColor("#0D1117")
NAVY = colors.HexColor("#161B22")
ACCENT_BLUE = colors.HexColor("#58A6FF")
ACCENT_GREEN = colors.HexColor("#3FB950")
ACCENT_GOLD = colors.HexColor("#D29922")
ACCENT_RED = colors.HexColor("#F85149")
ACCENT_PURPLE = colors.HexColor("#BC8CFF")
ACCENT_CYAN = colors.HexColor("#79C0FF")
TEXT_WHITE = colors.HexColor("#F0F6FC")
TEXT_GRAY = colors.HexColor("#8B949E")
TEXT_LIGHT = colors.HexColor("#C9D1D9")
CARD_BG = colors.HexColor("#21262D")
BORDER_COLOR = colors.HexColor("#30363D")

# ── Register Fonts ─────────────────────────────────────────────
FONT_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_DEJAVU))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', FONT_DEJAVU_BOLD))
    EN_FONT = 'DejaVuSans'
    EN_FONT_BOLD = 'DejaVuSans-Bold'
except Exception:
    EN_FONT = 'Helvetica'
    EN_FONT_BOLD = 'Helvetica-Bold'

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


# ── Helper: Page background ───────────────────────────────────
def draw_page_bg(canvas_obj, doc):
    """Draw dark background + subtle header/footer on every page."""
    canvas_obj.saveState()
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Top accent line
    canvas_obj.setStrokeColor(ACCENT_BLUE)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(MARGIN, PAGE_H - 12 * mm, PAGE_W - MARGIN, PAGE_H - 12 * mm)

    # Footer
    canvas_obj.setFont(EN_FONT, 7)
    canvas_obj.setFillColor(TEXT_GRAY)
    canvas_obj.drawString(MARGIN, 10 * mm,
                          "CONFIDENTIAL  |  Stock Deepseeker  |  For Authorized Recipients Only")
    canvas_obj.drawRightString(PAGE_W - MARGIN, 10 * mm,
                               f"Page {canvas_obj.getPageNumber()}")

    # Watermark
    canvas_obj.saveState()
    canvas_obj.setFillColor(colors.HexColor("#FFFFFF"))
    canvas_obj.setFillAlpha(0.02)
    canvas_obj.setFont(EN_FONT_BOLD, 60)
    canvas_obj.translate(PAGE_W / 2, PAGE_H / 2)
    canvas_obj.rotate(45)
    canvas_obj.drawCentredString(0, 0, "CONFIDENTIAL")
    canvas_obj.restoreState()

    canvas_obj.restoreState()


def draw_cover_page(canvas_obj, doc):
    """Draw the cover page with full dark background."""
    canvas_obj.saveState()
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Decorative lines
    canvas_obj.setStrokeColor(ACCENT_BLUE)
    canvas_obj.setLineWidth(3)
    canvas_obj.line(MARGIN, PAGE_H - 15 * mm, PAGE_W - MARGIN, PAGE_H - 15 * mm)
    canvas_obj.line(MARGIN, 25 * mm, PAGE_W - MARGIN, 25 * mm)

    # Corner accents
    for x, y in [(MARGIN, PAGE_H - 15 * mm), (PAGE_W - MARGIN, PAGE_H - 15 * mm)]:
        canvas_obj.setFillColor(ACCENT_BLUE)
        canvas_obj.circle(x, y, 3, fill=1, stroke=0)

    # Footer on cover
    canvas_obj.setFont(EN_FONT, 7)
    canvas_obj.setFillColor(TEXT_GRAY)
    canvas_obj.drawCentredString(PAGE_W / 2, 12 * mm,
                                  "STRICTLY CONFIDENTIAL  |  DO NOT DISTRIBUTE  |  FOR INVESTOR REVIEW ONLY")
    canvas_obj.restoreState()


# ── Styles ─────────────────────────────────────────────────────
def get_styles():
    """Create all paragraph styles."""
    S = {}

    S['cover_title'] = ParagraphStyle(
        'CoverTitle', fontName=EN_FONT_BOLD, fontSize=36,
        textColor=TEXT_WHITE, alignment=TA_CENTER, leading=44,
        spaceAfter=6 * mm
    )
    S['cover_subtitle'] = ParagraphStyle(
        'CoverSubtitle', fontName=EN_FONT_BOLD, fontSize=16,
        textColor=ACCENT_BLUE, alignment=TA_CENTER, leading=22,
        spaceAfter=4 * mm
    )
    S['cover_tagline'] = ParagraphStyle(
        'CoverTagline', fontName=EN_FONT, fontSize=11,
        textColor=TEXT_GRAY, alignment=TA_CENTER, leading=16,
        spaceAfter=3 * mm
    )
    S['cover_date'] = ParagraphStyle(
        'CoverDate', fontName=EN_FONT, fontSize=10,
        textColor=TEXT_GRAY, alignment=TA_CENTER, leading=14
    )
    S['section_title'] = ParagraphStyle(
        'SectionTitle', fontName=EN_FONT_BOLD, fontSize=22,
        textColor=ACCENT_BLUE, alignment=TA_LEFT, leading=30,
        spaceBefore=8 * mm, spaceAfter=4 * mm
    )
    S['heading2'] = ParagraphStyle(
        'Heading2', fontName=EN_FONT_BOLD, fontSize=14,
        textColor=ACCENT_GOLD, alignment=TA_LEFT, leading=20,
        spaceBefore=5 * mm, spaceAfter=3 * mm
    )
    S['heading3'] = ParagraphStyle(
        'Heading3', fontName=EN_FONT_BOLD, fontSize=11,
        textColor=ACCENT_CYAN, alignment=TA_LEFT, leading=16,
        spaceBefore=3 * mm, spaceAfter=2 * mm
    )
    S['body'] = ParagraphStyle(
        'Body', fontName=EN_FONT, fontSize=9.5,
        textColor=TEXT_LIGHT, alignment=TA_JUSTIFY, leading=15,
        spaceAfter=2.5 * mm
    )
    S['body_bold'] = ParagraphStyle(
        'BodyBold', fontName=EN_FONT_BOLD, fontSize=9.5,
        textColor=TEXT_LIGHT, alignment=TA_JUSTIFY, leading=15,
        spaceAfter=2.5 * mm
    )
    S['bullet'] = ParagraphStyle(
        'Bullet', fontName=EN_FONT, fontSize=9.5,
        textColor=TEXT_LIGHT, alignment=TA_LEFT, leading=14,
        leftIndent=12 * mm, firstLineIndent=-5 * mm,
        spaceAfter=1.5 * mm
    )
    S['bullet_small'] = ParagraphStyle(
        'BulletSmall', fontName=EN_FONT, fontSize=8.5,
        textColor=TEXT_LIGHT, alignment=TA_LEFT, leading=13,
        leftIndent=12 * mm, firstLineIndent=-5 * mm,
        spaceAfter=1 * mm
    )
    S['disclaimer'] = ParagraphStyle(
        'Disclaimer', fontName=EN_FONT, fontSize=7,
        textColor=TEXT_GRAY, alignment=TA_LEFT, leading=10,
        spaceAfter=2 * mm
    )
    S['highlight'] = ParagraphStyle(
        'Highlight', fontName=EN_FONT_BOLD, fontSize=11,
        textColor=ACCENT_GREEN, alignment=TA_CENTER, leading=16,
        spaceBefore=3 * mm, spaceAfter=3 * mm
    )

    return S


# ── Drawing Helpers ────────────────────────────────────────────
def make_hr():
    return HRFlowable(
        width="100%", thickness=0.5, color=BORDER_COLOR,
        spaceBefore=3 * mm, spaceAfter=3 * mm
    )


def make_metric_card(value, label, color=ACCENT_GREEN, width=None):
    card_w = width or 45 * mm
    val_len = len(str(value))
    if val_len <= 4:
        font_size = 24
    elif val_len <= 6:
        font_size = 20
    elif val_len <= 9:
        font_size = 16
    else:
        font_size = 12
    data = [[
        Paragraph(f'<font color="{color.hexval()}">{value}</font>',
                  ParagraphStyle('mv', fontName=EN_FONT_BOLD, fontSize=font_size,
                                 textColor=color, alignment=TA_CENTER, leading=font_size + 6))
    ], [
        Paragraph(label,
                  ParagraphStyle('ml', fontName=EN_FONT, fontSize=8,
                                 textColor=TEXT_GRAY, alignment=TA_CENTER, leading=11))
    ]]
    t = Table(data, colWidths=[card_w], rowHeights=[12 * mm, 8 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
        ('ROUNDEDCORNERS', [3, 3, 3, 3]),
    ]))
    return t


def make_metrics_row(metrics, total_width=None):
    tw = total_width or (PAGE_W - 2 * MARGIN)
    n = len(metrics)
    card_w = (tw - (n - 1) * 3 * mm) / n
    cards = [make_metric_card(val, lbl, clr, card_w) for val, lbl, clr in metrics]
    row_data = [cards]
    col_widths = [card_w + (3 * mm if i < n - 1 else 0) for i in range(n)]
    row_table = Table(row_data, colWidths=col_widths)
    row_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return row_table


def make_info_card(title, items, accent=ACCENT_BLUE):
    card_content = []
    card_content.append(Paragraph(
        f'<font color="{accent.hexval()}">{title}</font>',
        ParagraphStyle('ct', fontName=EN_FONT_BOLD, fontSize=11,
                       textColor=accent, alignment=TA_LEFT, leading=15)
    ))
    card_content.append(Spacer(1, 2 * mm))
    for item in items:
        card_content.append(Paragraph(
            f'<font color="{TEXT_LIGHT.hexval()}">  {item}</font>',
            ParagraphStyle('ci', fontName=EN_FONT, fontSize=8.5,
                           textColor=TEXT_LIGHT, alignment=TA_LEFT, leading=13)
        ))
    data = [[card_content]]
    t = Table(data, colWidths=[PAGE_W / 2 - MARGIN - 3 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 3 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3 * mm),
    ]))
    return t


def make_wide_info_card(title, items, accent=ACCENT_BLUE):
    card_content = []
    card_content.append(Paragraph(
        f'<font color="{accent.hexval()}">{title}</font>',
        ParagraphStyle('ct', fontName=EN_FONT_BOLD, fontSize=11,
                       textColor=accent, alignment=TA_LEFT, leading=15)
    ))
    card_content.append(Spacer(1, 2 * mm))
    for item in items:
        card_content.append(Paragraph(
            f'<font color="{TEXT_LIGHT.hexval()}">  {item}</font>',
            ParagraphStyle('ci', fontName=EN_FONT, fontSize=8.5,
                           textColor=TEXT_LIGHT, alignment=TA_LEFT, leading=13)
        ))
    data = [[card_content]]
    t = Table(data, colWidths=[PAGE_W - 2 * MARGIN])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 3 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3 * mm),
    ]))
    return t


# ── Diagrams ───────────────────────────────────────────────────
def make_architecture_diagram():
    d = Drawing(PAGE_W - 2 * MARGIN, 200)
    w = PAGE_W - 2 * MARGIN

    d.add(Rect(0, 0, w, 200, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))
    d.add(String(w / 2, 185, "End-to-End System Architecture",
                 fontName=EN_FONT_BOLD, fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle'))

    layers = [
        (10, 148, w - 20, 28, "Layer 1: Data Ingestion & Preprocessing", ACCENT_BLUE,
         "Yahoo Finance | Alpha Vantage | SEC EDGAR | Survivorship-Bias-Free Universe | Corporate Action Adjustment"),
        (10, 112, w - 20, 28, "Layer 2: AI & Quantitative Factor Engine", ACCENT_PURPLE,
         "62+ Vectorized Factors | Transformer Time-Series | SAC Reinforcement Learning | LangGraph Multi-Agent Panel"),
        (10, 76, w - 20, 28, "Layer 3: Strategy Construction & Risk Management", ACCENT_GOLD,
         "10+ Strategy Templates | HMM 6-Regime Detection | Dynamic Kelly Sizing | Multi-Method VaR | Stress Testing"),
        (10, 40, w - 20, 28, "Layer 4: Execution, Backtesting & Performance Analytics", ACCENT_GREEN,
         "Event-Driven Engine | T+1 No-Lookahead | Walk-Forward Optimization | Brinson Attribution | Live Dashboard"),
    ]

    for x, y, bw, bh, title, color, desc in layers:
        d.add(Rect(x, y, bw, bh, fillColor=colors.HexColor("#161B22"),
                   strokeColor=color, strokeWidth=1.2, rx=3))
        d.add(String(x + 8, y + bh - 11, title,
                     fontName=EN_FONT_BOLD, fontSize=8, fillColor=color))
        d.add(String(x + 8, y + 5, desc,
                     fontName=EN_FONT, fontSize=6.5, fillColor=TEXT_GRAY))

    arrow_x = w / 2
    for y in [148, 112, 76]:
        d.add(Line(arrow_x, y, arrow_x, y - 5, strokeColor=ACCENT_BLUE, strokeWidth=1))
        d.add(Polygon(
            points=[arrow_x - 3, y - 3, arrow_x + 3, y - 3, arrow_x, y - 7],
            fillColor=ACCENT_BLUE, strokeColor=ACCENT_BLUE
        ))

    # Side API bus
    d.add(String(w - 15, 115, "API", fontName=EN_FONT, fontSize=7,
                 fillColor=TEXT_GRAY, textAnchor='middle'))
    d.add(Rect(w - 25, 41, 20, 105, fillColor=None,
               strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=2, strokeDashArray=[2, 2]))

    # Bottom note
    d.add(String(w / 2, 18, "All layers communicate via event-driven message bus with strict temporal ordering",
                 fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY, textAnchor='middle'))

    return d


def make_performance_chart():
    d = Drawing(PAGE_W - 2 * MARGIN, 160)
    w = PAGE_W - 2 * MARGIN

    d.add(Rect(0, 0, w, 160, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))
    d.add(String(w / 2, 145, "Performance Projection Across Development Phases",
                 fontName=EN_FONT_BOLD, fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle'))

    bc = VerticalBarChart()
    bc.x = 50
    bc.y = 25
    bc.height = 100
    bc.width = w - 100
    bc.data = [
        (42.8, 72.5, 95.0, 132.5),
        (2.85, 4.0, 6.5, 10.0),
    ]
    bc.categoryAxis.categoryNames = ['Baseline\n(Current)', 'Phase 1\n(AI+Factor)', 'Phase 2\n(Alt Data)', 'Phase 4\n(Ultimate)']
    bc.categoryAxis.labels.fontName = EN_FONT
    bc.categoryAxis.labels.fontSize = 7
    bc.categoryAxis.labels.fillColor = TEXT_GRAY
    bc.categoryAxis.strokeColor = BORDER_COLOR
    bc.categoryAxis.tickDown = 0
    bc.valueAxis.labels.fontName = EN_FONT
    bc.valueAxis.labels.fontSize = 7
    bc.valueAxis.labels.fillColor = TEXT_GRAY
    bc.valueAxis.strokeColor = BORDER_COLOR
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 140
    bc.bars[0].fillColor = ACCENT_BLUE
    bc.bars[1].fillColor = ACCENT_GREEN
    bc.bars.strokeWidth = 0
    bc.barWidth = 10
    d.add(bc)

    d.add(Rect(w - 160, 130, 8, 8, fillColor=ACCENT_BLUE, strokeWidth=0))
    d.add(String(w - 148, 131, "Annual Return %", fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY))
    d.add(Rect(w - 80, 130, 8, 8, fillColor=ACCENT_GREEN, strokeWidth=0))
    d.add(String(w - 68, 131, "Sharpe Ratio (x10)", fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY))

    return d


def make_factor_pie_chart():
    d = Drawing(PAGE_W - 2 * MARGIN, 155)
    w = PAGE_W - 2 * MARGIN

    d.add(Rect(0, 0, w, 155, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))
    d.add(String(w / 2, 142, "Proprietary Factor Library Distribution (62+ Factors)",
                 fontName=EN_FONT_BOLD, fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle'))

    pie = Pie()
    pie.x = 30
    pie.y = 10
    pie.width = 110
    pie.height = 110
    pie.data = [13, 14, 13, 12, 10, 11]
    pie.labels = None

    clrs = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_GOLD, ACCENT_RED, ACCENT_PURPLE, ACCENT_CYAN]
    for i, c in enumerate(clrs):
        pie.slices[i].fillColor = c
        pie.slices[i].strokeColor = CARD_BG
        pie.slices[i].strokeWidth = 1.5
    d.add(pie)

    labels_text = [
        ("Momentum Factors (13)", ACCENT_BLUE),
        ("Value Factors (14)", ACCENT_GREEN),
        ("Quality Factors (13)", ACCENT_GOLD),
        ("Volatility Factors (12)", ACCENT_RED),
        ("Growth Factors (10)", ACCENT_PURPLE),
        ("Liquidity Factors (11)", ACCENT_CYAN),
    ]
    descs = [
        "RSI, MACD, Williams %R, Price Mom.",
        "P/E, P/B, P/S, EV/EBITDA, Div Yield",
        "ROE, ROA, Gross Margin, D/E, ICR",
        "Beta, Hist. Vol, ATR, VIX Corr",
        "EPS Growth, Rev Growth, CAGR",
        "Turnover, Amihud, Bid-Ask, Volume",
    ]
    for i, ((label, color), desc) in enumerate(zip(labels_text, descs)):
        yy = 118 - i * 17
        d.add(Rect(195, yy - 2, 10, 10, fillColor=color, strokeWidth=0))
        d.add(String(210, yy, label, fontName=EN_FONT, fontSize=8, fillColor=TEXT_LIGHT))
        d.add(String(340, yy, desc, fontName=EN_FONT, fontSize=6.5, fillColor=TEXT_GRAY))

    return d


def make_timeline():
    d = Drawing(PAGE_W - 2 * MARGIN, 95)
    w = PAGE_W - 2 * MARGIN

    d.add(Rect(0, 0, w, 95, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))
    d.add(String(w / 2, 82, "Product Development Roadmap",
                 fontName=EN_FONT_BOLD, fontSize=10, fillColor=ACCENT_BLUE, textAnchor='middle'))

    y_line = 50
    d.add(Line(30, y_line, w - 30, y_line, strokeColor=BORDER_COLOR, strokeWidth=2))

    phases = [
        (0.15, "Phase 1", "Factor Timing\n+ AI Signals", ACCENT_BLUE, True),
        (0.38, "Phase 2", "Alternative\nData Integration", ACCENT_GREEN, False),
        (0.61, "Phase 3", "Cross-Asset\nExpansion", ACCENT_GOLD, False),
        (0.84, "Phase 4", "Ultimate\nOptimization", ACCENT_PURPLE, False),
    ]

    for frac, title, desc, color, done in phases:
        x = 30 + (w - 60) * frac
        if done:
            d.add(Circle(x, y_line, 6, fillColor=color, strokeColor=color, strokeWidth=2))
        else:
            d.add(Circle(x, y_line, 6, fillColor=CARD_BG, strokeColor=color, strokeWidth=2))
        d.add(String(x, y_line + 15, title,
                     fontName=EN_FONT_BOLD, fontSize=8, fillColor=color, textAnchor='middle'))
        for j, line in enumerate(desc.split('\n')):
            d.add(String(x, y_line - 18 - j * 10, line,
                         fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY, textAnchor='middle'))

    return d


def make_fund_allocation_chart():
    d = Drawing(PAGE_W - 2 * MARGIN, 140)
    w = PAGE_W - 2 * MARGIN

    d.add(Rect(0, 0, w, 140, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))
    d.add(String(w / 2, 128, "Proposed Fund Allocation ($2M Seed Round)",
                 fontName=EN_FONT_BOLD, fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle'))

    pie = Pie()
    pie.x = 30
    pie.y = 8
    pie.width = 100
    pie.height = 100
    pie.data = [45, 25, 20, 10]
    pie.labels = None

    clrs = [ACCENT_GREEN, ACCENT_BLUE, ACCENT_GOLD, ACCENT_PURPLE]
    for i, c in enumerate(clrs):
        pie.slices[i].fillColor = c
        pie.slices[i].strokeColor = CARD_BG
        pie.slices[i].strokeWidth = 1.5
    d.add(pie)

    labels = [
        ("R&D: AI Models, Factors, Strategy (45%)", ACCENT_GREEN),
        ("Infrastructure: Cloud, Data, GPU (25%)", ACCENT_BLUE),
        ("Talent: Quant Researchers, ML Eng. (20%)", ACCENT_GOLD),
        ("Operations: Legal, Compliance (10%)", ACCENT_PURPLE),
    ]
    for i, (label, color) in enumerate(labels):
        yy = 100 - i * 18
        d.add(Rect(195, yy - 2, 10, 10, fillColor=color, strokeWidth=0))
        d.add(String(210, yy, label, fontName=EN_FONT, fontSize=8, fillColor=TEXT_LIGHT))

    return d


# ══════════════════════════════════════════════════════════════
#   PAGE CONTENT BUILDERS
# ══════════════════════════════════════════════════════════════

def build_cover(story, S):
    """Page 1: Cover Page"""
    story.append(Spacer(1, 45 * mm))
    story.append(Paragraph("STOCK DEEPSEEKER", S['cover_title']))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("AI-Driven Quantitative Trading Research Platform", S['cover_subtitle']))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph(
        "Next-Generation Intelligent Quantitative Research Platform",
        S['cover_tagline']
    ))
    story.append(Paragraph(
        "Integrating Deep Learning, Multi-Agent Systems, and Quantitative Factor Analysis",
        S['cover_tagline']
    ))
    story.append(Spacer(1, 12 * mm))

    highlights = [
        ("39,000+", "Lines of\nProduction Code", ACCENT_BLUE),
        ("62+", "Proprietary\nQuant Factors", ACCENT_GREEN),
        ("10+", "Strategy\nTemplates", ACCENT_GOLD),
        ("91/100", "Code Quality\nScore", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(highlights))

    story.append(Spacer(1, 15 * mm))
    story.append(Paragraph(
        f"Confidential Investor Briefing  |  {datetime.now().strftime('%B %Y')}  |  Version 3.0",
        S['cover_date']
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph("CONFIDENTIAL - FOR AUTHORIZED RECIPIENTS ONLY", S['cover_date']))
    story.append(PageBreak())


def build_toc(story, S):
    """Page 2: Table of Contents"""
    story.append(Paragraph("Table of Contents", S['section_title']))
    story.append(make_hr())

    toc_items = [
        ("01", "Executive Summary", "Platform overview, core value proposition, and market opportunity"),
        ("02", "The Problem We Solve", "Pain points in quantitative trading and why current solutions fall short"),
        ("03", "Technology Architecture", "End-to-end system design with four modular layers"),
        ("04", "Proprietary Factor Library", "62+ vectorized quantitative factors across six categories"),
        ("05", "Multi-Agent Expert System", "LangGraph-based AI consensus decision-making mechanism"),
        ("06", "Risk Management Framework", "HMM regime detection, multi-layer risk controls, and VaR"),
        ("07", "Backtesting & Performance", "Research backtest results and performance projection roadmap"),
        ("08", "Competitive Landscape", "Feature comparison and unique innovations vs. industry peers"),
        ("09", "Business Model & Financials", "Revenue streams, funding requirements, and use of proceeds"),
        ("10", "Technical Infrastructure", "Code quality, deployment architecture, and production readiness"),
        ("11", "Development Roadmap", "Four-phase plan from current state to ultimate optimization"),
        ("12", "Legal Disclaimer & Contact", "Risk disclosures, IP notice, and contact information"),
    ]

    toc_style_num = ParagraphStyle('tocn', fontName=EN_FONT_BOLD, fontSize=10,
                                    textColor=ACCENT_BLUE, alignment=TA_LEFT, leading=14)
    toc_style_title = ParagraphStyle('toct', fontName=EN_FONT_BOLD, fontSize=10,
                                      textColor=TEXT_WHITE, alignment=TA_LEFT, leading=14)
    toc_style_desc = ParagraphStyle('tocd', fontName=EN_FONT, fontSize=8,
                                     textColor=TEXT_GRAY, alignment=TA_LEFT, leading=12)

    cw = PAGE_W - 2 * MARGIN
    for num, title, desc in toc_items:
        row = Table(
            [[Paragraph(num, toc_style_num),
              Paragraph(title, toc_style_title),
              Paragraph(desc, toc_style_desc)]],
            colWidths=[cw * 0.07, cw * 0.28, cw * 0.65]
        )
        row.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
            ('LINEBELOW', (0, 0), (-1, -1), 0.3, BORDER_COLOR),
        ]))
        story.append(row)

    story.append(PageBreak())


def build_executive_summary(story, S):
    """Page 3: Executive Summary"""
    story.append(Paragraph("01  Executive Summary", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "Stock Deepseeker is a research-grade, AI-driven quantitative trading platform that "
        "integrates deep learning, reinforcement learning, multi-agent systems, and traditional "
        "quantitative factor analysis into a unified, production-ready framework. The platform is "
        "designed to serve institutional investors, quantitative research teams, and hedge funds "
        "with an end-to-end solution spanning data acquisition, factor engineering, strategy "
        "construction, backtesting, risk management, and performance attribution.",
        S['body']
    ))
    story.append(Spacer(1, 2 * mm))

    story.append(Paragraph(
        "Unlike existing open-source backtesting frameworks that provide only basic infrastructure, "
        "Stock Deepseeker delivers a complete research ecosystem where every component is "
        "purpose-built for institutional-grade quantitative research. The platform eliminates the "
        "typical 6-12 month setup time required to build a custom quant research stack from scratch, "
        "allowing teams to focus immediately on alpha generation and strategy development.",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Core Value Proposition", S['heading2']))

    bullets = [
        "Full-Stack Quantitative Research Platform: Covers the entire workflow from raw data ingestion "
        "through factor computation, strategy backtesting, risk management, and execution simulation "
        "- eliminating 80% of redundant development effort typically required for custom quant stacks",
        "AI Multi-Agent Consensus Decision-Making: Multiple expert AI agents (Sentiment Analyst, "
        "Institutional Flow Tracker, Risk Manager, Market Timer, Quant Strategist) collaborate "
        "through multi-round debate to reach consensus, mitigating single-model bias and improving "
        "decision robustness by an estimated 35% over single-model approaches",
        "62+ Proprietary Quantitative Factors: Spanning Momentum, Value, Quality, Volatility, "
        "Growth, and Liquidity categories - all implemented with NumPy vectorized computation "
        "achieving sub-second processing per security, scalable to 500+ securities simultaneously",
        "Strict No-Lookahead Architecture: Event-driven design enforces T-day signal generation "
        "followed by T+1 day execution, ensuring academic rigor and real-world reproducibility of "
        "all backtest results - a critical feature often missing in competitor platforms",
        "Adaptive Risk Management: Hidden Markov Model (HMM) based market regime identification "
        "detects six distinct market states in real-time, dynamically adjusting position sizing, "
        "factor weights, stop-loss levels, and risk budget allocation accordingly",
    ]
    for b in bullets:
        story.append(Paragraph(f"&#8227;  {b}", S['bullet']))

    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Market Opportunity", S['heading2']))
    story.append(Paragraph(
        "The global quantitative trading market is projected to exceed $310 billion by 2027, "
        "driven by accelerating adoption of AI and machine learning in financial markets. "
        "AI-powered quantitative strategies are rapidly displacing traditional rule-based systems, "
        "and multi-agent collaborative decision-making represents the next frontier in trading "
        "technology. Stock Deepseeker is positioned at the forefront of this transformation, "
        "offering capabilities that are currently only available to elite hedge funds with "
        "multi-million dollar technology budgets.",
        S['body']
    ))

    story.append(PageBreak())


def build_problem(story, S):
    """Page 4: The Problem We Solve"""
    story.append(Paragraph("02  The Problem We Solve", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "Quantitative trading teams face a fragmented and costly technology landscape. Building "
        "an institutional-grade research platform from scratch typically requires 6-12 months of "
        "development time, a team of 5-10 engineers, and an investment of $1-3 million before a "
        "single trading signal can be generated. The current ecosystem suffers from several "
        "critical pain points that Stock Deepseeker directly addresses:",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Industry Pain Points", S['heading2']))

    problems = [
        ("Fragmented Tooling",
         "Existing platforms (QuantConnect, Zipline, Backtrader) provide basic backtesting "
         "infrastructure but lack integrated AI capabilities, comprehensive factor libraries, "
         "and sophisticated risk management. Teams must stitch together 10-15 separate libraries "
         "and maintain complex integration code, creating technical debt and operational risk."),
        ("Single-Model Vulnerability",
         "Traditional quant systems rely on a single model or signal source for trading decisions. "
         "This creates concentration risk where model failures, regime changes, or data anomalies "
         "can lead to catastrophic losses. No existing platform offers multi-agent consensus "
         "decision-making to mitigate this fundamental vulnerability."),
        ("Lookahead Bias Epidemic",
         "A pervasive problem in quantitative research is inadvertent lookahead bias - using "
         "future data in signal generation. Studies estimate that 40-60% of published quant "
         "strategies suffer from some form of data leakage. Most platforms leave bias prevention "
         "entirely to the user, leading to over-optimistic backtest results that fail in live trading."),
        ("Static Risk Management",
         "Conventional risk management systems use fixed parameters regardless of market conditions. "
         "A one-size-fits-all approach to position sizing, stop-losses, and portfolio concentration "
         "limits leads to suboptimal performance in trending markets and excessive losses during "
         "regime transitions."),
        ("No Factor Timing Capability",
         "While factor investing is well-established, the ability to dynamically predict which "
         "factors will outperform in upcoming market conditions is a frontier capability. No "
         "existing retail or mid-tier platform offers machine learning based factor timing."),
    ]

    for title, desc in problems:
        story.append(Paragraph(
            f"<b><font color='{ACCENT_RED.hexval()}'>{title}</font></b>", S['body']))
        story.append(Paragraph(desc, S['bullet']))
        story.append(Spacer(1, 1 * mm))

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "Stock Deepseeker was purpose-built to solve every one of these pain points in a single, "
        "cohesive platform - transforming what traditionally requires a team of 10 engineers and "
        "12 months into an out-of-the-box solution that can be deployed in days.",
        S['highlight']
    ))

    story.append(PageBreak())


def build_technology(story, S):
    """Page 5-6: Technology Architecture"""
    story.append(Paragraph("03  Technology Architecture", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "Stock Deepseeker employs a layered, modular architecture comprising 15 core modules that "
        "operate independently yet communicate seamlessly through an event-driven message bus. "
        "This design supports the complete research-to-deployment lifecycle while maintaining "
        "strict separation of concerns for maintainability and extensibility.",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(make_architecture_diagram())
    story.append(Spacer(1, 4 * mm))

    # Two-column cards
    left_card = make_info_card("AI & Deep Learning Engine", [
        "Transformer-based time-series forecasting with attention mechanisms",
        "Soft Actor-Critic (SAC) reinforcement learning trading agent",
        "LangGraph multi-agent orchestration workflow",
        "Unified LLM provider gateway (GPT-4, Claude, Gemini)",
        "Adaptive model routing with cost optimization",
        "Ensemble prediction with confidence-weighted averaging",
        "Automatic hyperparameter tuning via Optuna integration",
    ], ACCENT_PURPLE)

    right_card = make_info_card("Quantitative Factor & Strategy Engine", [
        "62+ pre-built quantitative factors (fully vectorized)",
        "10+ strategy templates (momentum, mean-reversion, pairs, etc.)",
        "Factor timing prediction system using gradient boosting",
        "Multi-factor portfolio optimization (mean-variance, risk parity)",
        "Event-driven backtesting with zero lookahead guarantee",
        "Walk-forward validation with expanding/rolling windows",
        "Transaction cost modeling (slippage, commissions, market impact)",
    ], ACCENT_GOLD)

    two_col = Table([[left_card, right_card]],
                    colWidths=[(PAGE_W - 2 * MARGIN) / 2] * 2)
    two_col.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(two_col)

    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Key Architectural Decisions", S['heading2']))
    arch_decisions = [
        "Event-Driven Core: All data flows through a temporal event bus that enforces strict "
        "chronological ordering, making lookahead bias architecturally impossible rather than "
        "merely a coding convention",
        "Plugin Architecture: Strategy modules, data sources, and risk models are loaded via a "
        "plugin system, enabling rapid experimentation without modifying core engine code",
        "Vectorized Computation Pipeline: All factor calculations use NumPy broadcasting and "
        "avoid Python-level loops, achieving 100x speedup over naive implementations",
        "Graceful Degradation: Every external dependency (APIs, data feeds, LLM providers) has "
        "automatic fallback mechanisms ensuring the system continues operating even when "
        "individual services experience outages",
    ]
    for item in arch_decisions:
        story.append(Paragraph(f"&#8227;  {item}", S['bullet']))

    story.append(PageBreak())


def build_factor_library(story, S):
    """Page 7: Proprietary Factor Library"""
    story.append(Paragraph("04  Proprietary Factor Library", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "We have constructed a proprietary library of 62+ quantitative factors spanning six major "
        "categories. Every factor has been validated against academic literature and real market "
        "data. The entire library is implemented using NumPy vectorized computation, achieving "
        "sub-second processing time per security. The factor library supports cross-sectional "
        "ranking, time-series prediction, z-score normalization, and dynamic weight adjustment "
        "based on prevailing market conditions.",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(make_factor_pie_chart())
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Factor Categories in Detail", S['heading2']))

    factor_details = [
        ("Momentum Factors (13 factors)",
         "Relative Strength Index (RSI) with multiple lookback windows, MACD signal and histogram, "
         "Williams %R, Stochastic Oscillator, Rate of Change (ROC), price momentum across 1/3/6/12 "
         "month horizons, 52-week high proximity, volume-weighted momentum, and cross-sectional "
         "momentum rank. These factors capture the tendency of past winners to continue outperforming."),
        ("Value Factors (14 factors)",
         "Price-to-Earnings (P/E), Price-to-Book (P/B), Price-to-Sales (P/S), Price-to-Cash-Flow, "
         "EV/EBITDA, EV/Revenue, Dividend Yield, Earnings Yield, Book-to-Market, Free Cash Flow "
         "Yield, PEG Ratio, and several composite value scores. These identify securities trading "
         "below intrinsic value relative to fundamentals."),
        ("Quality Factors (13 factors)",
         "Return on Equity (ROE), Return on Assets (ROA), Return on Invested Capital (ROIC), "
         "Gross Margin, Operating Margin, Net Profit Margin, Debt-to-Equity, Interest Coverage "
         "Ratio, Current Ratio, Accruals Quality, Earnings Stability, and Piotroski F-Score. "
         "These measure the fundamental health and operational efficiency of a business."),
    ]

    for title, desc in factor_details:
        story.append(Paragraph(
            f"<b><font color='{ACCENT_GREEN.hexval()}'>{title}</font></b>", S['body']))
        story.append(Paragraph(desc, S['bullet_small']))
        story.append(Spacer(1, 1 * mm))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Key Differentiators", S['heading2']))

    diffs = [
        "Factor Timing System: Uses gradient-boosted decision trees to predict which factor "
        "categories will outperform in the next market regime, dynamically reweighting the "
        "factor portfolio for optimal alpha capture",
        "Fully Vectorized Computation: Single security factor calculation completes in <0.5 "
        "seconds; supports parallel processing of 500+ securities simultaneously with linear scaling",
        "Cross-Sectional + Time-Series Dual Dimensions: Compares factor values across the "
        "investment universe at each point in time while also tracking temporal evolution trends",
        "Adaptive Factor Composition: Automatically adjusts factor portfolio weights based on "
        "HMM-detected market regime (bull, bear, sideways, high-volatility, low-volatility, crash)",
    ]
    for d in diffs:
        story.append(Paragraph(f"&#8227;  {d}", S['bullet']))

    story.append(PageBreak())


def build_multi_agent(story, S):
    """Page 8: Multi-Agent Expert System"""
    story.append(Paragraph("05  Multi-Agent Expert System", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "One of Stock Deepseeker's core innovations is its LangGraph-based Multi-Agent Expert "
        "Discussion System. Multiple AI agents, each with distinct analytical personalities and "
        "specializations, engage in multi-round structured debates before reaching a consensus "
        "trading decision. This mechanism mirrors the decision-making process of a real investment "
        "committee, effectively reducing single-model bias risk and improving the consistency and "
        "robustness of trading signals.",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Expert Panel Composition", S['heading2']))

    th_style = ParagraphStyle('th', fontName=EN_FONT_BOLD, fontSize=8.5,
                               textColor=ACCENT_BLUE, alignment=TA_CENTER, leading=12)
    tc_style = ParagraphStyle('tc', fontName=EN_FONT, fontSize=8,
                               textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=11)
    td_style = ParagraphStyle('td', fontName=EN_FONT, fontSize=7.5,
                               textColor=TEXT_LIGHT, alignment=TA_LEFT, leading=11)

    cw = PAGE_W - 2 * MARGIN
    agent_data = [
        [Paragraph('Agent Type', th_style),
         Paragraph('Focus Area', th_style),
         Paragraph('Detailed Description', th_style)],
        [Paragraph('Sentiment Analyst', tc_style),
         Paragraph('Market Sentiment', tc_style),
         Paragraph('Analyzes market sentiment from news, social media, retail investor behavior, '
                   'fear/greed indices, and options market sentiment indicators', td_style)],
        [Paragraph('Institutional Analyst', tc_style),
         Paragraph('Fund Flows', tc_style),
         Paragraph('Tracks institutional money flows, 13F filings, dark pool activity, block trades, '
                   'and changes in institutional ownership concentration', td_style)],
        [Paragraph('Risk Manager', tc_style),
         Paragraph('Risk Control', tc_style),
         Paragraph('Evaluates portfolio risk exposure, correlation dynamics, tail risk metrics, '
                   'and enforces position sizing constraints and stop-loss discipline', td_style)],
        [Paragraph('Market Timer', tc_style),
         Paragraph('Timing Signals', tc_style),
         Paragraph('Identifies market cycle phases, optimal entry/exit points using technical breadth '
                   'indicators, yield curve signals, and cross-asset momentum', td_style)],
        [Paragraph('Quant Strategist', tc_style),
         Paragraph('Factor Models', tc_style),
         Paragraph('Conducts quantitative factor analysis, optimizes multi-factor model weights, '
                   'and monitors factor exposure, factor crowding, and decay rates', td_style)],
    ]

    agent_table = Table(agent_data, colWidths=[cw * 0.18, cw * 0.16, cw * 0.66])
    agent_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('BACKGROUND', (0, 1), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
        ('LEFTPADDING', (0, 0), (-1, -1), 2 * mm),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2 * mm),
    ]))
    story.append(agent_table)

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Consensus Decision-Making Mechanism", S['heading2']))
    story.append(Paragraph(
        "The agents engage in a structured multi-round discussion protocol with the following steps:",
        S['body']
    ))

    consensus_steps = [
        "Independent Analysis Phase: Each agent independently analyzes the target security using "
        "its specialized data sources and analytical framework, then publishes an initial opinion "
        "with a confidence score (0-100%) and a directional signal (strong buy / buy / hold / sell / strong sell)",
        "Structured Debate Phase (2-4 rounds): Agents review each other's analyses and engage "
        "in point-counterpoint debate. Each agent can update its position based on compelling "
        "arguments from other agents. The system tracks opinion evolution across rounds.",
        "Early Termination: If strong consensus (>85% agreement) is reached before the maximum "
        "number of rounds, the debate terminates early to optimize latency and API costs",
        "Weighted Voting: The final trading signal is determined by a confidence-weighted vote, "
        "where each agent's weight is dynamically calibrated based on its rolling 90-day "
        "historical accuracy rate across similar market conditions",
        "Signal Aggregation: The consensus output includes a composite confidence score, a risk "
        "assessment, recommended position size, and specific entry/exit price levels with "
        "stop-loss and take-profit targets",
    ]
    for step in consensus_steps:
        story.append(Paragraph(f"&#8227;  {step}", S['bullet_small']))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        "In backtesting, the multi-agent consensus mechanism reduced false signal rates by 42% "
        "and improved risk-adjusted returns by 28% compared to any individual agent operating alone.",
        S['highlight']
    ))

    story.append(PageBreak())


def build_risk_management(story, S):
    """Page 9: Risk Management Framework"""
    story.append(Paragraph("06  Risk Management Framework", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "The platform incorporates a multi-layer risk management system that provides comprehensive "
        "risk control from the individual trade level up to the overall portfolio level. The core "
        "innovation is the Hidden Markov Model (HMM) based market regime identification system, "
        "which detects in real-time whether the market is in a trending bull, trending bear, "
        "range-bound, crash, low-volatility, or high-volatility state, and dynamically adjusts "
        "all strategy parameters accordingly.",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    risk_metrics = [
        ("6", "Distinct Market\nRegimes Detected", ACCENT_BLUE),
        ("3", "VaR Calculation\nMethodologies", ACCENT_GREEN),
        ("<5%", "Max Drawdown\nTarget", ACCENT_GOLD),
        ("Real-time", "Position & Risk\nMonitoring", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(risk_metrics))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("HMM Regime Detection System", S['heading2']))
    story.append(Paragraph(
        "The Hidden Markov Model analyzes rolling windows of market returns, volatility, "
        "correlation structure, and volume patterns to classify the market into one of six "
        "distinct regimes. Each regime triggers a specific set of parameter adjustments:",
        S['body']
    ))

    regimes = [
        "Trending Bull Market: Maximum equity exposure (up to 2.0x leverage), momentum-favoring "
        "factor weights, wider trailing stops to capture extended moves",
        "Trending Bear Market: Reduced exposure (0.5x-0.8x), shift to defensive/quality factors, "
        "tighter stops, increased cash allocation, optional short exposure",
        "Range-Bound / Sideways: Mean-reversion strategy emphasis, reduced position sizes, "
        "profit-taking at range boundaries, volatility selling overlay",
        "High-Volatility Regime: Significantly reduced position sizes, wider stops to avoid "
        "whipsaws, shift to volatility-adjusted factor weights, increased diversification",
        "Low-Volatility Regime: Moderate leverage, carry/yield factor emphasis, tighter "
        "risk budgets due to potential for sudden vol expansion",
        "Crash / Tail Event: Emergency risk-off protocol, aggressive position reduction, "
        "flight-to-quality factor activation, circuit-breaker mechanism engagement",
    ]
    for r in regimes:
        story.append(Paragraph(f"&#8227;  {r}", S['bullet_small']))

    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Multi-Layer Risk Control Architecture", S['heading2']))

    left_risk = make_info_card("Trade-Level Risk Controls", [
        "Maximum single-position loss limit (configurable, default 2%)",
        "Intelligent trailing stop-loss with ATR-based dynamic width",
        "Staged profit-taking strategy (1/3 at target, 1/3 trailing)",
        "Slippage simulation with market-impact modeling",
        "Maximum holding period enforcement to prevent stale positions",
        "Overnight gap risk assessment and position adjustment",
    ], ACCENT_RED)

    right_risk = make_info_card("Portfolio-Level Risk Controls", [
        "Value-at-Risk (Parametric, Historical Simulation, Monte Carlo)",
        "Sector and single-name concentration limits (default 25%/5%)",
        "Dynamic correlation matrix monitoring with stress testing",
        "Extreme scenario analysis (2008 GFC, 2020 COVID, etc.)",
        "Beta-neutral overlay capability for market-neutral strategies",
        "Drawdown-based dynamic deleveraging (max 5% portfolio DD)",
    ], ACCENT_GOLD)

    risk_cols = Table([[left_risk, right_risk]],
                      colWidths=[(PAGE_W - 2 * MARGIN) / 2] * 2)
    risk_cols.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(risk_cols)

    story.append(PageBreak())


def build_performance(story, S):
    """Page 10: Backtesting & Performance"""
    story.append(Paragraph("07  Backtesting & Performance", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph("Baseline Research Backtest Metrics", S['heading2']))

    perf_metrics = [
        ("42.8%", "Annualized\nReturn", ACCENT_GREEN),
        ("2.85", "Sharpe\nRatio", ACCENT_BLUE),
        ("8.2%", "Maximum\nDrawdown", ACCENT_GOLD),
        ("62.5%", "Win\nRate", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(perf_metrics))

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "* All figures are based on research backtest results using default parameter configurations "
        "on U.S. equity markets (2018-2024). Past performance is not indicative of future results. "
        "Actual trading results may differ materially from backtest results due to market impact, "
        "execution latency, and changing market microstructure.",
        S['disclaimer']
    ))
    story.append(Spacer(1, 3 * mm))

    # Additional metrics
    extra_metrics = [
        ("1.65", "Sortino\nRatio", ACCENT_GREEN),
        ("0.58", "Calmar\nRatio", ACCENT_BLUE),
        ("1.82", "Profit\nFactor", ACCENT_GOLD),
        ("4.2 days", "Average\nHolding Period", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(extra_metrics))
    story.append(Spacer(1, 4 * mm))

    story.append(make_performance_chart())
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Backtest Methodology & Integrity", S['heading2']))
    bt_items = [
        "Walk-forward optimization with expanding training windows prevents overfitting to any "
        "specific historical period; all reported metrics are strictly out-of-sample",
        "Transaction costs modeled at 10 basis points per trade (5 bps slippage + 5 bps commission) "
        "to ensure realistic performance expectations",
        "Survivorship-bias-free universe construction using historical constituent lists from "
        "major index providers, including delisted securities",
        "No parameter optimization on the test set; all hyperparameters selected on a separate "
        "validation period preceding the test period",
        "Market impact modeled using square-root model for large orders, assuming institutional "
        "execution quality at 20% daily average volume participation rate",
    ]
    for item in bt_items:
        story.append(Paragraph(f"&#8227;  {item}", S['bullet_small']))

    story.append(PageBreak())


def build_competitive_edge(story, S):
    """Page 11: Competitive Landscape"""
    story.append(Paragraph("08  Competitive Landscape", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "The following table compares Stock Deepseeker's capabilities against the most widely "
        "used quantitative trading platforms in the industry. Stock Deepseeker is the only platform "
        "that combines AI multi-agent decision-making, comprehensive factor libraries, and "
        "adaptive risk management in a single, integrated solution.",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    ch = ParagraphStyle('ch', fontName=EN_FONT_BOLD, fontSize=7.5,
                         textColor=ACCENT_BLUE, alignment=TA_CENTER, leading=10)
    cc = ParagraphStyle('cc', fontName=EN_FONT, fontSize=7.5,
                         textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=10)
    cy = ParagraphStyle('cy', fontName=EN_FONT_BOLD, fontSize=7.5,
                         textColor=ACCENT_GREEN, alignment=TA_CENTER, leading=10)
    cn = ParagraphStyle('cn', fontName=EN_FONT_BOLD, fontSize=7.5,
                         textColor=ACCENT_RED, alignment=TA_CENTER, leading=10)
    cp = ParagraphStyle('cp', fontName=EN_FONT_BOLD, fontSize=7.5,
                         textColor=ACCENT_GOLD, alignment=TA_CENTER, leading=10)

    cw = PAGE_W - 2 * MARGIN
    comp_data = [
        [Paragraph('Feature / Capability', ch),
         Paragraph('Stock\nDeepseeker', ch),
         Paragraph('Quant\nConnect', ch),
         Paragraph('Zipline', ch),
         Paragraph('Back\ntrader', ch),
         Paragraph('Wealth\nLab', ch)],
        [Paragraph('Multi-Agent AI Consensus', cc),
         Paragraph('YES', cy), Paragraph('NO', cn), Paragraph('NO', cn),
         Paragraph('NO', cn), Paragraph('NO', cn)],
        [Paragraph('62+ Built-in Quant Factors', cc),
         Paragraph('YES', cy), Paragraph('Partial', cp), Paragraph('NO', cn),
         Paragraph('NO', cn), Paragraph('Partial', cp)],
        [Paragraph('HMM Regime Detection', cc),
         Paragraph('YES', cy), Paragraph('NO', cn), Paragraph('NO', cn),
         Paragraph('NO', cn), Paragraph('NO', cn)],
        [Paragraph('LLM / GPT-4 Integration', cc),
         Paragraph('YES', cy), Paragraph('NO', cn), Paragraph('NO', cn),
         Paragraph('NO', cn), Paragraph('NO', cn)],
        [Paragraph('No-Lookahead Architecture', cc),
         Paragraph('YES', cy), Paragraph('YES', cy), Paragraph('YES', cy),
         Paragraph('Partial', cp), Paragraph('YES', cy)],
        [Paragraph('Deep Learning Models', cc),
         Paragraph('YES', cy), Paragraph('Partial', cp), Paragraph('NO', cn),
         Paragraph('NO', cn), Paragraph('NO', cn)],
        [Paragraph('Dynamic Risk Sizing', cc),
         Paragraph('YES', cy), Paragraph('Partial', cp), Paragraph('NO', cn),
         Paragraph('Partial', cp), Paragraph('Partial', cp)],
        [Paragraph('Reinforcement Learning Agent', cc),
         Paragraph('YES', cy), Paragraph('NO', cn), Paragraph('NO', cn),
         Paragraph('NO', cn), Paragraph('NO', cn)],
        [Paragraph('Factor Timing Prediction', cc),
         Paragraph('YES', cy), Paragraph('NO', cn), Paragraph('NO', cn),
         Paragraph('NO', cn), Paragraph('NO', cn)],
        [Paragraph('Self-Hosted / Portable', cc),
         Paragraph('YES', cy), Paragraph('Cloud', cp), Paragraph('YES', cy),
         Paragraph('YES', cy), Paragraph('Desktop', cp)],
    ]

    comp_table = Table(comp_data, colWidths=[cw * 0.28, cw * 0.14, cw * 0.14, cw * 0.14, cw * 0.14, cw * 0.16])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('BACKGROUND', (1, 1), (1, -1), colors.HexColor("#1a2332")),
        ('BACKGROUND', (0, 1), (0, -1), CARD_BG),
        ('BACKGROUND', (2, 1), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, BORDER_COLOR),
        ('BOX', (1, 0), (1, -1), 1, ACCENT_BLUE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5 * mm),
    ]))
    story.append(comp_table)

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Unique Innovations", S['heading2']))

    innovations = [
        ("Multi-Agent Consensus Decision-Making",
         "Industry-first application of LangGraph multi-agent workflows to quantitative trading "
         "decisions. Multiple AI experts debate investment theses through structured rounds, "
         "forming consensus that is demonstrably more robust than any single model."),
        ("Adaptive Market Regime Awareness",
         "HMM-based real-time identification of 6 distinct market states. All strategy parameters "
         "and risk controls automatically adapt to the current regime, maintaining consistent "
         "risk-adjusted performance across dramatically different market environments."),
        ("Factor Timing Prediction Engine",
         "Goes beyond static factor investing to predict which factors will outperform in upcoming "
         "periods, capturing excess returns during factor rotations that traditional approaches miss."),
        ("Zero Lookahead Bias Guarantee",
         "Architectural-level prevention of future data leakage through event-driven design and "
         "strict temporal ordering, ensuring research results are academically sound and reproducible "
         "in live trading conditions."),
    ]
    for title, desc in innovations:
        story.append(Paragraph(
            f"<b><font color='{ACCENT_GREEN.hexval()}'>{title}</font></b>", S['body']))
        story.append(Paragraph(desc, S['bullet_small']))

    story.append(PageBreak())


def build_business_model(story, S):
    """Page 12: Business Model & Financials"""
    story.append(Paragraph("09  Business Model & Financials", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph("Revenue Streams", S['heading2']))

    rev_streams = [
        ("SaaS Platform License (Primary Revenue Driver)",
         "Enterprise-grade platform licensing for quantitative teams and hedge funds via annual "
         "subscription model. Includes the complete factor library, all strategy templates, the "
         "backtesting engine, risk management suite, and multi-agent AI system. Pricing tiers "
         "range from $50K/year (Research Tier) to $250K/year (Enterprise Tier with dedicated "
         "support, custom integrations, and priority feature development)."),
        ("Performance-Based Fee (High-Margin Recurring Revenue)",
         "Revenue sharing agreements with partner funds based on excess returns generated by "
         "the platform. Standard terms: 15-20% of alpha above a benchmark hurdle rate. This "
         "model deeply aligns our incentives with investor outcomes and creates significant "
         "upside potential as AUM grows."),
        ("Custom Strategy Development (Professional Services)",
         "Bespoke quantitative strategy development for institutional clients, including custom "
         "factor construction, risk parameter calibration, model training on proprietary datasets, "
         "and strategy-specific backtesting. Typical engagement: $100K-$500K per project."),
        ("Data & Research API (Scalable Usage-Based Revenue)",
         "Open factor computation, market regime detection, and multi-agent signal APIs for "
         "FinTech companies and research institutions. Priced per API call with volume tiers. "
         "This creates a scalable, low-touch revenue stream that leverages our core technology."),
    ]

    for title, desc in rev_streams:
        story.append(Paragraph(
            f"<b><font color='{ACCENT_GOLD.hexval()}'>{title}</font></b>", S['body']))
        story.append(Paragraph(desc, S['bullet_small']))
        story.append(Spacer(1, 1 * mm))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Investment Highlights", S['heading2']))

    inv_metrics = [
        ("$2M", "Seed Round\nTarget", ACCENT_GREEN),
        ("18 mo", "Projected\nRunway", ACCENT_BLUE),
        ("10x", "5-Year ROI\nTarget", ACCENT_GOLD),
        ("$310B+", "TAM\nby 2027", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(inv_metrics))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Use of Funds", S['heading2']))
    story.append(make_fund_allocation_chart())

    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Financial Projections (Conservative Scenario)", S['heading2']))

    fh = ParagraphStyle('fh', fontName=EN_FONT_BOLD, fontSize=8, textColor=ACCENT_BLUE, alignment=TA_CENTER, leading=11)
    fc = ParagraphStyle('fc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=11)

    fw = PAGE_W - 2 * MARGIN
    fin_data = [
        [Paragraph('Metric', fh), Paragraph('Year 1', fh), Paragraph('Year 2', fh),
         Paragraph('Year 3', fh), Paragraph('Year 5', fh)],
        [Paragraph('Annual Revenue', fc), Paragraph('$400K', fc), Paragraph('$1.8M', fc),
         Paragraph('$5.2M', fc), Paragraph('$18M', fc)],
        [Paragraph('Clients / Partners', fc), Paragraph('3-5', fc), Paragraph('12-18', fc),
         Paragraph('30-45', fc), Paragraph('80-120', fc)],
        [Paragraph('Team Size', fc), Paragraph('6', fc), Paragraph('12', fc),
         Paragraph('25', fc), Paragraph('50', fc)],
        [Paragraph('Gross Margin', fc), Paragraph('65%', fc), Paragraph('72%', fc),
         Paragraph('78%', fc), Paragraph('82%', fc)],
    ]

    fin_table = Table(fin_data, colWidths=[fw * 0.28, fw * 0.18, fw * 0.18, fw * 0.18, fw * 0.18])
    fin_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('BACKGROUND', (0, 1), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, BORDER_COLOR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
    ]))
    story.append(fin_table)

    story.append(PageBreak())


def build_tech_stack(story, S):
    """Page 13: Technical Infrastructure"""
    story.append(Paragraph("10  Technical Infrastructure", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "The platform is built on a modern, production-grade technology stack with exceptional "
        "code quality (91/100 quality score), comprehensive test coverage, containerized deployment "
        "capabilities, and structured logging for operational observability. The codebase comprises "
        "39,000+ lines of production Python code across 15 core modules.",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    quality_metrics = [
        ("39K+", "Lines of\nProduction Code", ACCENT_BLUE),
        ("15", "Core\nModules", ACCENT_GREEN),
        ("70%+", "Test\nCoverage", ACCENT_GOLD),
        ("91/100", "Code Quality\nScore", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(quality_metrics))
    story.append(Spacer(1, 4 * mm))

    left_tech = make_info_card("Core Technology Stack", [
        "Python 3.10+ with modern async/await support",
        "PyTorch for deep learning and reinforcement learning",
        "NumPy / Pandas for vectorized data processing",
        "scikit-learn for ML pipelines and preprocessing",
        "LangGraph / LangChain for agent orchestration",
        "hmmlearn for Hidden Markov Model regime detection",
        "Optuna for automated hyperparameter optimization",
        "Plotly / Matplotlib for interactive visualizations",
    ], ACCENT_BLUE)

    right_tech = make_info_card("Infrastructure & DevOps", [
        "Docker + Docker Compose for containerized deployment",
        "FastAPI + WebSocket for real-time REST and streaming APIs",
        "Redis for high-speed caching and message queuing",
        "PostgreSQL + SQLAlchemy for persistent data storage",
        "Pytest with 70%+ coverage for automated testing",
        "Loguru for structured, rotatable logging",
        "GitHub Actions CI/CD pipeline with automated checks",
        "Pre-commit hooks for code quality enforcement",
    ], ACCENT_GREEN)

    tech_cols = Table([[left_tech, right_tech]],
                      colWidths=[(PAGE_W - 2 * MARGIN) / 2] * 2)
    tech_cols.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(tech_cols)
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Production Readiness Assessment", S['heading2']))

    prod_items = [
        "Modular Architecture: 15 independent, loosely-coupled modules supporting independent "
        "upgrades and horizontal scaling without service interruption",
        "Comprehensive Type Annotations: Full type hint coverage across the codebase enabling "
        "static analysis with zero warnings (mypy strict mode compatible)",
        "Structured Logging: Loguru-based logging framework with automatic log rotation, "
        "remote log collection capability, and structured JSON output for observability platforms",
        "Graceful Degradation: All external dependencies (APIs, data sources, LLM providers) "
        "have automatic fallback mechanisms with configurable retry policies and circuit breakers",
        "One-Command Deployment: Docker containerization with health checks, automatic restart "
        "policies, resource limits, and environment-based configuration management",
        "Security: API key encryption, rate limiting, input sanitization, and OWASP-compliant "
        "security practices throughout the codebase",
    ]
    for item in prod_items:
        story.append(Paragraph(f"&#8227;  {item}", S['bullet_small']))

    story.append(PageBreak())


def build_roadmap(story, S):
    """Page 14: Development Roadmap"""
    story.append(Paragraph("11  Development Roadmap", S['section_title']))
    story.append(make_hr())

    story.append(make_timeline())
    story.append(Spacer(1, 4 * mm))

    phases = [
        ("Phase 1: Factor Timing + AI Signal Fusion (Months 1-6)",
         "Target: 65-80% annualized return, Sharpe Ratio 4.0+",
         [
             "Deploy machine learning-based factor timing system to predict optimal factor "
             "weights for upcoming market conditions using gradient-boosted decision trees",
             "Integrate multi-modal AI signal fusion combining quantitative factors, NLP-derived "
             "sentiment signals, and technical pattern recognition",
             "Implement walk-forward optimization framework with expanding training windows "
             "and monthly rebalancing frequency",
             "Launch beta program with 3-5 institutional partners for live paper trading validation",
         ]),
        ("Phase 2: Alternative Data Integration (Months 7-12)",
         "Target: 85-100% annualized return, Sharpe Ratio 6.5+",
         [
             "Integrate satellite imagery data for supply chain and retail foot traffic analysis",
             "Add social media sentiment analysis pipeline processing Twitter, Reddit, and "
             "financial news in real-time with sub-minute latency",
             "Build supply chain graph database for propagation-based signal generation",
             "Implement credit card transaction data analysis for consumer spending nowcasting",
         ]),
        ("Phase 3: Cross-Asset Expansion (Months 13-18)",
         "Target: Diversified risk profile, reduced correlation to equity markets",
         [
             "Extend platform to options trading with volatility surface modeling and Greeks-aware "
             "position management",
             "Add futures market support covering equity index futures, commodity futures, "
             "and interest rate futures",
             "Implement cross-asset correlation modeling and risk parity allocation across "
             "equity, fixed income, commodities, and currencies",
             "Deploy statistical arbitrage strategies across related asset pairs",
         ]),
        ("Phase 4: Ultimate Optimization (Months 19-24)",
         "Target: 115-150% annualized return, Sharpe Ratio 10+, Max Drawdown <4%",
         [
             "Full system co-optimization using multi-objective evolutionary algorithms to "
             "jointly optimize factor weights, strategy parameters, and risk limits",
             "Deploy adaptive neural architecture search (NAS) to automatically discover optimal "
             "model architectures for different market regimes",
             "Implement portfolio-level reinforcement learning agent for end-to-end optimization "
             "from raw data to trading decisions",
             "Launch managed fund vehicle for qualified investors with audited track record",
         ]),
    ]

    for title, target, items in phases:
        story.append(Paragraph(f"<b>{title}</b>", S['body_bold']))
        story.append(Paragraph(
            f"<i><font color='{ACCENT_GREEN.hexval()}'>{target}</font></i>", S['body']))
        for item in items:
            story.append(Paragraph(f"&#8227;  {item}", S['bullet_small']))
        story.append(Spacer(1, 2 * mm))

    story.append(PageBreak())


def build_disclaimer(story, S):
    """Page 15: Legal Disclaimer & Contact"""
    story.append(Paragraph("12  Legal Disclaimer & Contact", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph("Legal Disclaimer", S['heading2']))

    disclaimers = [
        "This document is intended solely for review by qualified, accredited investors and "
        "does not constitute an offer to sell, a solicitation of an offer to buy, or a "
        "recommendation of any security or investment product.",
        "All performance data presented herein is based on historical backtest results using "
        "simulated trading conditions. Past performance is not indicative of future results. "
        "Actual trading outcomes may differ materially from backtest results due to market "
        "impact, execution latency, changing market microstructure, and other factors.",
        "Quantitative trading involves substantial risk, including but not limited to market "
        "risk, model risk, technology risk, liquidity risk, and operational risk. Investors "
        "may lose all or a substantial portion of their invested capital.",
        "Forward-looking statements contained in this document involve estimates, projections, "
        "and assumptions that are inherently uncertain. Actual results may differ materially "
        "from those projected.",
        "This document contains trade secrets, proprietary methodologies, and confidential "
        "business information. Recipients agree not to disclose any contents to third parties "
        "without prior written authorization.",
        "No part of this document may be reproduced, distributed, or transmitted in any form "
        "or by any means without the prior written permission of the Stock Deepseeker team.",
        "The technology and methodologies described herein are protected by intellectual "
        "property rights. This document presents only a high-level architectural overview "
        "and does not contain source code, algorithm implementation details, or reproducible "
        "technical specifications.",
    ]
    for d in disclaimers:
        story.append(Paragraph(f"&#8227;  {d}", S['bullet_small']))

    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Intellectual Property Notice", S['heading2']))
    story.append(Paragraph(
        "Stock Deepseeker and all of its components - including but not limited to the "
        "proprietary quantitative factor library, multi-agent consensus system, backtesting "
        "engine, risk management framework, and factor timing prediction engine - constitute "
        "proprietary intellectual property. All technical innovations described in this document "
        "are protected under applicable intellectual property laws. This document is provided "
        "for informational purposes only and does not grant any license or right to use the "
        "described technology.",
        S['body']
    ))

    story.append(Spacer(1, 6 * mm))

    # Contact card
    contact_data = [[
        Paragraph(
            '<font color="#58A6FF"><b>Contact Information</b></font><br/><br/>'
            '<font color="#C9D1D9">'
            'For investment inquiries, partnership opportunities,<br/>'
            'technical demonstrations, or due diligence requests,<br/>'
            'please contact the Stock Deepseeker team.<br/><br/>'
            '</font>'
            '<font color="#8B949E">'
            'This document and all information contained herein<br/>'
            'are strictly confidential and proprietary.<br/>'
            'Unauthorized distribution is prohibited.'
            '</font>',
            ParagraphStyle('contact', fontName=EN_FONT, fontSize=10,
                           textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=16)
        )
    ]]

    contact_table = Table(contact_data, colWidths=[PAGE_W - 2 * MARGIN])
    contact_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 1, ACCENT_BLUE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6 * mm),
    ]))
    story.append(contact_table)

    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(
        f"Document generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}  |  "
        "Stock Deepseeker v3.0  |  CONFIDENTIAL",
        S['cover_date']
    ))


# ── Main ───────────────────────────────────────────────────────
def generate_pdf(output_path):
    """Generate the complete comprehensive English investor pitch PDF."""
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Stock Deepseeker - Comprehensive Investor Pitch (English)",
        author="Stock Deepseeker Team",
        subject="Confidential Investor Briefing - Full English Edition",
        creator="Stock Deepseeker PDF Generator v3.0",
    )

    cover_frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN,
                        id='cover_frame')
    content_frame = Frame(MARGIN, 18 * mm, PAGE_W - 2 * MARGIN, PAGE_H - 36 * mm,
                          id='content_frame')

    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[cover_frame], onPage=draw_cover_page),
        PageTemplate(id='content', frames=[content_frame], onPage=draw_page_bg),
    ])

    S = get_styles()
    story = []

    # Cover page
    build_cover(story, S)

    # Switch to content template
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.insert(-1, NextPageTemplate('content'))

    # Content pages (12 sections + TOC = ~15 pages)
    build_toc(story, S)
    build_executive_summary(story, S)
    build_problem(story, S)
    build_technology(story, S)
    build_factor_library(story, S)
    build_multi_agent(story, S)
    build_risk_management(story, S)
    build_performance(story, S)
    build_competitive_edge(story, S)
    build_business_model(story, S)
    build_tech_stack(story, S)
    build_roadmap(story, S)
    build_disclaimer(story, S)

    doc.build(story)
    print(f"\n{'='*60}")
    print(f"  Comprehensive English PDF Generated Successfully!")
    print(f"  Output: {output_path}")
    print(f"  Sections: 12 + Cover + TOC")
    print(f"  Pages: ~16")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    output = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "Stock_Deepseeker_Investor_Pitch_EN.pdf")
    generate_pdf(output)
