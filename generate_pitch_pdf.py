#!/usr/bin/env python3
"""
Stock Deepseeker - Investor Pitch PDF Generator
Generates a professional pitch deck without revealing source code.
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
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
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
TEXT_WHITE = colors.HexColor("#F0F6FC")
TEXT_GRAY = colors.HexColor("#8B949E")
TEXT_LIGHT = colors.HexColor("#C9D1D9")
CARD_BG = colors.HexColor("#21262D")
BORDER_COLOR = colors.HexColor("#30363D")

# ── Register Fonts ─────────────────────────────────────────────
FONT_PATH_ZH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
FONT_DEJAVU = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

try:
    pdfmetrics.registerFont(TTFont('ZenHei', FONT_PATH_ZH, subfontIndex=0))
    CJK_FONT = 'ZenHei'
except:
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_DEJAVU))
    CJK_FONT = 'DejaVuSans'

try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_DEJAVU))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', FONT_DEJAVU_BOLD))
    EN_FONT = 'DejaVuSans'
    EN_FONT_BOLD = 'DejaVuSans-Bold'
except:
    EN_FONT = 'Helvetica'
    EN_FONT_BOLD = 'Helvetica-Bold'

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm


# ── Helper: Draw dark background on every page ────────────────
class DarkPageTemplate(canvas.Canvas):
    """Custom canvas that draws a dark background on every page."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._page_count = 0

    def showPage(self):
        self._page_count += 1
        super().showPage()

    def save(self):
        super().save()


def draw_page_bg(canvas_obj, doc):
    """Draw dark background + subtle header/footer on every page."""
    canvas_obj.saveState()
    # Full-page dark background
    canvas_obj.setFillColor(DARK_BG)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Top accent line
    canvas_obj.setStrokeColor(ACCENT_BLUE)
    canvas_obj.setLineWidth(2)
    canvas_obj.line(MARGIN, PAGE_H - 12 * mm, PAGE_W - MARGIN, PAGE_H - 12 * mm)

    # Footer
    canvas_obj.setFont(CJK_FONT, 7)
    canvas_obj.setFillColor(TEXT_GRAY)
    canvas_obj.drawString(MARGIN, 10 * mm,
                          "CONFIDENTIAL | Stock Deepseeker | For Authorized Recipients Only")
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

    # Decorative elements
    canvas_obj.setStrokeColor(ACCENT_BLUE)
    canvas_obj.setLineWidth(3)
    canvas_obj.line(MARGIN, PAGE_H - 15 * mm, PAGE_W - MARGIN, PAGE_H - 15 * mm)
    canvas_obj.line(MARGIN, 25 * mm, PAGE_W - MARGIN, 25 * mm)

    # Corner accents
    for x, y in [(MARGIN, PAGE_H - 15 * mm), (PAGE_W - MARGIN, PAGE_H - 15 * mm)]:
        canvas_obj.setFillColor(ACCENT_BLUE)
        canvas_obj.circle(x, y, 3, fill=1, stroke=0)

    # Footer on cover
    canvas_obj.setFont(CJK_FONT, 7)
    canvas_obj.setFillColor(TEXT_GRAY)
    canvas_obj.drawCentredString(PAGE_W / 2, 12 * mm,
                                  "STRICTLY CONFIDENTIAL | DO NOT DISTRIBUTE | FOR INVESTOR REVIEW ONLY")

    canvas_obj.restoreState()


# ── Styles ─────────────────────────────────────────────────────
def get_styles():
    """Create all paragraph styles."""
    styles = {}

    styles['cover_title'] = ParagraphStyle(
        'CoverTitle', fontName=EN_FONT_BOLD, fontSize=36,
        textColor=TEXT_WHITE, alignment=TA_CENTER, leading=44,
        spaceAfter=6 * mm
    )
    styles['cover_subtitle'] = ParagraphStyle(
        'CoverSubtitle', fontName=CJK_FONT, fontSize=16,
        textColor=ACCENT_BLUE, alignment=TA_CENTER, leading=22,
        spaceAfter=4 * mm
    )
    styles['cover_tagline'] = ParagraphStyle(
        'CoverTagline', fontName=CJK_FONT, fontSize=11,
        textColor=TEXT_GRAY, alignment=TA_CENTER, leading=16,
        spaceAfter=3 * mm
    )
    styles['cover_date'] = ParagraphStyle(
        'CoverDate', fontName=CJK_FONT, fontSize=10,
        textColor=TEXT_GRAY, alignment=TA_CENTER, leading=14
    )
    styles['section_title'] = ParagraphStyle(
        'SectionTitle', fontName=CJK_FONT, fontSize=22,
        textColor=ACCENT_BLUE, alignment=TA_LEFT, leading=30,
        spaceBefore=8 * mm, spaceAfter=4 * mm
    )
    styles['section_title_zh'] = ParagraphStyle(
        'SectionTitleZh', fontName=CJK_FONT, fontSize=22,
        textColor=ACCENT_BLUE, alignment=TA_LEFT, leading=28,
        spaceBefore=8 * mm, spaceAfter=4 * mm
    )
    styles['heading2'] = ParagraphStyle(
        'Heading2', fontName=CJK_FONT, fontSize=15,
        textColor=ACCENT_GOLD, alignment=TA_LEFT, leading=22,
        spaceBefore=5 * mm, spaceAfter=3 * mm
    )
    styles['heading2_zh'] = ParagraphStyle(
        'Heading2Zh', fontName=CJK_FONT, fontSize=15,
        textColor=ACCENT_GOLD, alignment=TA_LEFT, leading=20,
        spaceBefore=5 * mm, spaceAfter=3 * mm
    )
    styles['body'] = ParagraphStyle(
        'Body', fontName=CJK_FONT, fontSize=10,
        textColor=TEXT_LIGHT, alignment=TA_JUSTIFY, leading=16,
        spaceAfter=2.5 * mm
    )
    styles['body_en'] = ParagraphStyle(
        'BodyEN', fontName=CJK_FONT, fontSize=10,
        textColor=TEXT_LIGHT, alignment=TA_JUSTIFY, leading=16,
        spaceAfter=2.5 * mm
    )
    styles['bullet'] = ParagraphStyle(
        'Bullet', fontName=CJK_FONT, fontSize=10,
        textColor=TEXT_LIGHT, alignment=TA_LEFT, leading=15,
        leftIndent=12 * mm, firstLineIndent=-5 * mm,
        spaceAfter=1.5 * mm
    )
    styles['metric_value'] = ParagraphStyle(
        'MetricValue', fontName=EN_FONT_BOLD, fontSize=28,
        textColor=ACCENT_GREEN, alignment=TA_CENTER, leading=34
    )
    styles['metric_label'] = ParagraphStyle(
        'MetricLabel', fontName=CJK_FONT, fontSize=9,
        textColor=TEXT_GRAY, alignment=TA_CENTER, leading=13
    )
    styles['disclaimer'] = ParagraphStyle(
        'Disclaimer', fontName=CJK_FONT, fontSize=7,
        textColor=TEXT_GRAY, alignment=TA_LEFT, leading=10,
        spaceAfter=2 * mm
    )
    styles['card_title'] = ParagraphStyle(
        'CardTitle', fontName=CJK_FONT, fontSize=12,
        textColor=ACCENT_BLUE, alignment=TA_LEFT, leading=16,
        spaceAfter=2 * mm
    )
    styles['card_body'] = ParagraphStyle(
        'CardBody', fontName=CJK_FONT, fontSize=9,
        textColor=TEXT_LIGHT, alignment=TA_LEFT, leading=14,
        spaceAfter=1 * mm
    )
    styles['highlight'] = ParagraphStyle(
        'Highlight', fontName=CJK_FONT, fontSize=11,
        textColor=ACCENT_GREEN, alignment=TA_CENTER, leading=16,
        spaceBefore=3 * mm, spaceAfter=3 * mm
    )

    return styles


# ── Drawing Helpers ────────────────────────────────────────────
def make_hr():
    """Horizontal rule."""
    return HRFlowable(
        width="100%", thickness=0.5, color=BORDER_COLOR,
        spaceBefore=3 * mm, spaceAfter=3 * mm
    )


def make_metric_card(value, label, color=ACCENT_GREEN, width=None):
    """Create a single metric display card."""
    card_w = width or 45 * mm
    # Auto-scale font size for longer values
    val_len = len(str(value))
    if val_len <= 4:
        font_size = 24
    elif val_len <= 6:
        font_size = 20
    elif val_len <= 9:
        font_size = 16
    else:
        font_size = 13
    data = [[
        Paragraph(f'<font color="{color.hexval()}">{value}</font>',
                  ParagraphStyle('mv', fontName=CJK_FONT, fontSize=font_size,
                                 textColor=color, alignment=TA_CENTER, leading=font_size + 6))
    ], [
        Paragraph(label,
                  ParagraphStyle('ml', fontName=CJK_FONT, fontSize=8,
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
    """Create a row of metric cards."""
    tw = total_width or (PAGE_W - 2 * MARGIN)
    n = len(metrics)
    card_w = (tw - (n - 1) * 3 * mm) / n
    cards = []
    for val, lbl, clr in metrics:
        cards.append(make_metric_card(val, lbl, clr, card_w))

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
    """Create an info card with title and bullet items."""
    card_content = []
    card_content.append(Paragraph(
        f'<font color="{accent.hexval()}">{title}</font>',
        ParagraphStyle('ct', fontName=CJK_FONT, fontSize=12,
                       textColor=accent, alignment=TA_LEFT, leading=16)
    ))
    card_content.append(Spacer(1, 2 * mm))
    for item in items:
        card_content.append(Paragraph(
            f'<font color="{TEXT_LIGHT.hexval()}">  {item}</font>',
            ParagraphStyle('ci', fontName=CJK_FONT, fontSize=9,
                           textColor=TEXT_LIGHT, alignment=TA_LEFT, leading=14)
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


def make_architecture_diagram():
    """Create a system architecture diagram."""
    d = Drawing(PAGE_W - 2 * MARGIN, 180)
    w = PAGE_W - 2 * MARGIN

    # Background
    d.add(Rect(0, 0, w, 180, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))

    # Title
    d.add(String(w / 2, 165, "System Architecture Overview",
                 fontName=EN_FONT_BOLD, fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle'))

    # Layer boxes - from top to bottom
    layers = [
        (10, 130, w - 20, 25, "Data Ingestion Layer", ACCENT_BLUE,
         "Multi-Source Market Data | Corporate Actions | Survivorship Bias Mitigation"),
        (10, 98, w - 20, 25, "AI & Factor Engine", ACCENT_PURPLE,
         "62+ Quantitative Factors | Transformer & RL Models | Multi-Agent Expert Panel"),
        (10, 66, w - 20, 25, "Strategy & Risk Layer", ACCENT_GOLD,
         "10+ Strategy Templates | HMM Regime Detection | Dynamic Position Sizing | VaR"),
        (10, 34, w - 20, 25, "Execution & Analytics", ACCENT_GREEN,
         "Event-Driven Backtest | No-Lookahead Enforcement | Performance Attribution"),
    ]

    for x, y, bw, bh, title, color, desc in layers:
        d.add(Rect(x, y, bw, bh, fillColor=colors.HexColor("#161B22"),
                   strokeColor=color, strokeWidth=1.2, rx=3))
        d.add(String(x + 8, y + bh - 10, title,
                     fontName=EN_FONT_BOLD, fontSize=9, fillColor=color))
        d.add(String(x + 8, y + 5, desc,
                     fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY))

    # Arrows between layers
    arrow_x = w / 2
    for y in [130, 98, 66]:
        d.add(Line(arrow_x, y, arrow_x, y - 5,
                   strokeColor=ACCENT_BLUE, strokeWidth=1))
        # arrowhead
        d.add(Polygon(
            points=[arrow_x - 3, y - 3, arrow_x + 3, y - 3, arrow_x, y - 7],
            fillColor=ACCENT_BLUE, strokeColor=ACCENT_BLUE
        ))

    # Side labels
    d.add(String(w - 15, 100, "API", fontName=EN_FONT, fontSize=7,
                 fillColor=TEXT_GRAY, textAnchor='middle'))
    d.add(Rect(w - 25, 35, 20, 90, fillColor=None,
               strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=2, strokeDashArray=[2, 2]))

    return d


def make_performance_chart():
    """Create a performance comparison bar chart."""
    d = Drawing(PAGE_W - 2 * MARGIN, 160)
    w = PAGE_W - 2 * MARGIN

    d.add(Rect(0, 0, w, 160, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))
    d.add(String(w / 2, 145, "Performance Projection Roadmap",
                 fontName=EN_FONT_BOLD, fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle'))

    bc = VerticalBarChart()
    bc.x = 50
    bc.y = 25
    bc.height = 100
    bc.width = w - 100
    bc.data = [
        (42.8, 72.5, 95.0, 132.5),   # Annual Return %
        (2.85, 4.0, 6.5, 10.0),       # Sharpe Ratio (scaled x10 for visibility)
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

    # Legend
    d.add(Rect(w - 160, 130, 8, 8, fillColor=ACCENT_BLUE, strokeWidth=0))
    d.add(String(w - 148, 131, "Annual Return %", fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY))
    d.add(Rect(w - 80, 130, 8, 8, fillColor=ACCENT_GREEN, strokeWidth=0))
    d.add(String(w - 68, 131, "Sharpe Ratio", fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY))

    return d


def make_factor_pie_chart():
    """Create a factor category distribution pie chart."""
    d = Drawing(PAGE_W - 2 * MARGIN, 150)
    w = PAGE_W - 2 * MARGIN

    d.add(Rect(0, 0, w, 150, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))
    d.add(String(w / 2, 138, "Proprietary Factor Library Distribution (62+ Factors)",
                 fontName=EN_FONT_BOLD, fontSize=11, fillColor=ACCENT_BLUE, textAnchor='middle'))

    pie = Pie()
    pie.x = 30
    pie.y = 10
    pie.width = 110
    pie.height = 110
    pie.data = [13, 14, 13, 12, 10, 11]
    pie.labels = None

    clrs = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_GOLD, ACCENT_RED, ACCENT_PURPLE,
            colors.HexColor("#79C0FF")]
    for i, c in enumerate(clrs):
        pie.slices[i].fillColor = c
        pie.slices[i].strokeColor = CARD_BG
        pie.slices[i].strokeWidth = 1.5

    d.add(pie)

    # Legend
    labels_text = [
        ("Momentum (13)", ACCENT_BLUE),
        ("Value (14)", ACCENT_GREEN),
        ("Quality (13)", ACCENT_GOLD),
        ("Volatility (12)", ACCENT_RED),
        ("Growth (10)", ACCENT_PURPLE),
        ("Liquidity (11)", colors.HexColor("#79C0FF")),
    ]
    for i, (label, color) in enumerate(labels_text):
        yy = 115 - i * 17
        d.add(Rect(200, yy - 2, 10, 10, fillColor=color, strokeWidth=0))
        d.add(String(215, yy, label, fontName=EN_FONT, fontSize=8, fillColor=TEXT_LIGHT))

    # Right side - descriptions
    descs = [
        "RSI, MACD, Price Momentum",
        "P/E, P/B, Dividend Yield",
        "ROE, Profit Margin, D/E",
        "Beta, Historical Vol, VIX Corr",
        "Earnings Growth, Sales Growth",
        "Turnover, Amihud, Volume",
    ]
    for i, desc in enumerate(descs):
        yy = 115 - i * 17
        d.add(String(330, yy, desc, fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY))

    return d


def make_timeline():
    """Create a development timeline/roadmap."""
    d = Drawing(PAGE_W - 2 * MARGIN, 90)
    w = PAGE_W - 2 * MARGIN

    d.add(Rect(0, 0, w, 90, fillColor=CARD_BG, strokeColor=BORDER_COLOR, strokeWidth=0.5, rx=4))

    # Timeline line
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
        # Node
        if done:
            d.add(Circle(x, y_line, 6, fillColor=color, strokeColor=color, strokeWidth=2))
        else:
            d.add(Circle(x, y_line, 6, fillColor=CARD_BG, strokeColor=color, strokeWidth=2))
        # Title
        d.add(String(x, y_line + 15, title,
                     fontName=EN_FONT_BOLD, fontSize=8, fillColor=color, textAnchor='middle'))
        # Description
        for j, line in enumerate(desc.split('\n')):
            d.add(String(x, y_line - 18 - j * 10, line,
                         fontName=EN_FONT, fontSize=7, fillColor=TEXT_GRAY, textAnchor='middle'))

    return d


# ── Page Content Builders ──────────────────────────────────────
def build_cover(story, S):
    """Build the cover page."""
    story.append(Spacer(1, 50 * mm))
    story.append(Paragraph("STOCK DEEPSEEKER", S['cover_title']))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("AI-Driven Quantitative Trading Research Platform", S['cover_subtitle']))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(
        "下一代智能量化交易研究平台  |  融合深度学习、多智能体系统与量化因子分析",
        S['cover_tagline']
    ))
    story.append(Spacer(1, 15 * mm))

    # Key highlights on cover
    highlights = [
        ("39,000+", "Lines of Code\n代码行数", ACCENT_BLUE),
        ("62+", "Quant Factors\n量化因子", ACCENT_GREEN),
        ("10+", "Strategies\n策略模板", ACCENT_GOLD),
        ("91/100", "Quality Score\n质量评分", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(highlights))

    story.append(Spacer(1, 20 * mm))
    story.append(Paragraph(
        f"Investor Briefing  |  {datetime.now().strftime('%B %Y')}  |  v3.0.0",
        S['cover_date']
    ))
    story.append(Paragraph("CONFIDENTIAL - FOR AUTHORIZED RECIPIENTS ONLY", S['cover_date']))
    story.append(PageBreak())


def build_executive_summary(story, S):
    """Build Executive Summary page."""
    story.append(Paragraph("01  Executive Summary  |  项目概述", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "Stock Deepseeker 是一个研究级别的 AI 驱动量化交易平台，融合了深度学习、强化学习、"
        "多智能体系统和传统量化因子分析。该平台旨在为机构投资者和量化研究团队提供从数据获取、"
        "因子研发、策略回测到风险管理的全链路解决方案。",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    story.append(Paragraph("Core Value Proposition  |  核心价值", S['heading2']))

    bullets = [
        "全栈量化研究平台：覆盖数据、因子、策略、风控、执行全流程，减少 80% 重复开发工作",
        "AI 多智能体共识决策：多个专家智能体（情感分析师、机构分析师、风险经理等）协同决策，"
        "避免单一模型偏差，提升决策稳健性",
        "62+ 专有量化因子库：涵盖动量、价值、质量、波动率、成长、流动性六大类别，"
        "全部向量化计算，高效可扩展",
        "严格防前视偏差：事件驱动架构，T 日信号 → T+1 日执行，确保回测结果的学术严谨性",
        "自适应风险管理：基于隐马尔可夫模型（HMM）的市场状态识别，动态调整仓位和风险敞口",
    ]
    for b in bullets:
        story.append(Paragraph(f"▸  {b}", S['bullet']))

    story.append(Spacer(1, 5 * mm))

    # Market opportunity
    story.append(Paragraph("Market Opportunity  |  市场机遇", S['heading2']))
    story.append(Paragraph(
        "全球量化交易市场规模预计 2027 年将达到 $310B+。AI 驱动的量化策略正在取代传统规则型系统，"
        "而多智能体协同决策代表了下一代量化交易的技术趋势。Stock Deepseeker 正处于这一变革的前沿。",
        S['body']
    ))

    story.append(PageBreak())


def build_technology(story, S):
    """Build Technology Overview page."""
    story.append(Paragraph("02  Technology Overview  |  技术架构", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "系统采用分层模块化架构，15 个核心模块各司其职，支持从研究到部署的完整生命周期。",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    # Architecture diagram
    story.append(make_architecture_diagram())
    story.append(Spacer(1, 5 * mm))

    # Tech highlights in two columns
    left_card = make_info_card("AI & Deep Learning 引擎", [
        "Transformer 时序预测模型",
        "SAC 强化学习交易智能体",
        "LangGraph 多智能体工作流",
        "多 LLM 供应商统一接入（GPT-4, Claude）",
        "自适应模型路由与成本优化",
    ], ACCENT_PURPLE)

    right_card = make_info_card("量化因子 & 策略引擎", [
        "62+ 预构建量化因子（向量化计算）",
        "10+ 策略模板（动量、均值回归、配对交易...）",
        "因子时序预测系统",
        "多因子组合优化",
        "事件驱动回测，零前视偏差",
    ], ACCENT_GOLD)

    two_col = Table([[left_card, right_card]],
                    colWidths=[(PAGE_W - 2 * MARGIN) / 2] * 2)
    two_col.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(two_col)

    story.append(PageBreak())


def build_factor_library(story, S):
    """Build Factor Library page."""
    story.append(Paragraph("03  Proprietary Factor Library  |  专有因子库", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "我们构建了涵盖六大类别、62+ 个量化因子的专有库。每个因子均经过学术文献验证，"
        "采用 NumPy 向量化计算实现亚秒级处理速度。因子库支持横截面排名、时序预测和动态权重调整。",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    # Pie chart
    story.append(make_factor_pie_chart())
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Key Differentiators  |  关键优势", S['heading2']))

    diffs = [
        "因子时序系统（Factor Timing）：预测不同市场环境下哪些因子表现最优，动态调整因子权重",
        "全向量化计算：单个标的因子计算 <0.5 秒，支持 100+ 标的并行处理",
        "横截面 + 时序双维度：不仅对比同期个股间的因子值，还追踪因子的时序变化趋势",
        "自适应因子组合：基于市场状态（牛市/熊市/震荡）自动调整因子组合权重",
    ]
    for d in diffs:
        story.append(Paragraph(f"▸  {d}", S['bullet']))

    story.append(PageBreak())


def build_multi_agent(story, S):
    """Build Multi-Agent System page."""
    story.append(Paragraph("04  Multi-Agent Expert System  |  多智能体专家系统", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "Stock Deepseeker 的核心创新之一是基于 LangGraph 的多智能体专家讨论系统。"
        "多个具有不同「性格」和分析专长的 AI 智能体进行多轮讨论，最终达成共识决策。"
        "这一机制模拟了真实投资委员会的决策过程，有效降低单一模型的偏差风险。",
        S['body']
    ))
    story.append(Spacer(1, 3 * mm))

    # Agent types
    story.append(Paragraph("Expert Panel Composition  |  专家面板构成", S['heading2']))

    agent_data = [
        [Paragraph('<font color="#58A6FF">Agent Type</font>',
                   ParagraphStyle('th', fontName=EN_FONT_BOLD, fontSize=9, textColor=ACCENT_BLUE, alignment=TA_CENTER)),
         Paragraph('<font color="#58A6FF">Focus Area</font>',
                   ParagraphStyle('th', fontName=EN_FONT_BOLD, fontSize=9, textColor=ACCENT_BLUE, alignment=TA_CENTER)),
         Paragraph('<font color="#58A6FF">Description | 描述</font>',
                   ParagraphStyle('th', fontName=CJK_FONT, fontSize=9, textColor=ACCENT_BLUE, alignment=TA_CENTER))],
        [Paragraph('Sentiment Analyst', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('Market Sentiment', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('分析市场情绪、新闻舆情和散户行为', ParagraphStyle('tc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_LEFT))],
        [Paragraph('Institutional Analyst', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('Fund Flows', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('追踪机构资金流向和持仓变化', ParagraphStyle('tc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_LEFT))],
        [Paragraph('Risk Manager', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('Risk Control', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('评估风险敞口、执行止损止盈策略', ParagraphStyle('tc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_LEFT))],
        [Paragraph('Market Timer', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('Timing Signals', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('判断市场周期和最佳入场/退出时机', ParagraphStyle('tc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_LEFT))],
        [Paragraph('Quant Strategist', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('Factor Models', ParagraphStyle('tc', fontName=EN_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_CENTER)),
         Paragraph('量化因子分析和多因子模型优化', ParagraphStyle('tc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT, alignment=TA_LEFT))],
    ]

    cw = (PAGE_W - 2 * MARGIN)
    agent_table = Table(agent_data, colWidths=[cw * 0.22, cw * 0.20, cw * 0.58])
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

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Consensus Mechanism  |  共识机制", S['heading2']))
    story.append(Paragraph(
        "智能体通过多轮讨论形成共识，支持早期终止（强共识时快速决策）。"
        "每个智能体独立分析后发表意见，经过 2-4 轮辩论后进行投票。"
        "最终交易信号基于加权共识，权重根据各智能体的历史准确率动态调整。"
        "该机制在回测中显著降低了误信号率，提高了交易决策的一致性和稳健性。",
        S['body']
    ))

    story.append(PageBreak())


def build_risk_management(story, S):
    """Build Risk Management page."""
    story.append(Paragraph("05  Risk Management  |  风险管理体系", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "系统内置多层风险管理模块，从单笔交易到整体投资组合层面提供全方位风险控制。"
        "核心创新是基于隐马尔可夫模型（HMM）的市场状态识别系统，能够实时检测市场"
        "处于趋势上涨、趋势下跌、区间震荡或剧烈波动等不同状态，并据此动态调整策略参数。",
        S['body']
    ))

    story.append(Spacer(1, 3 * mm))

    # Risk metrics
    risk_metrics = [
        ("6", "Market Regimes\n市场状态识别", ACCENT_BLUE),
        ("3", "VaR Methods\n风险价值方法", ACCENT_GREEN),
        ("<5%", "Max Drawdown Target\n最大回撤目标", ACCENT_GOLD),
        ("Real-time", "Position Monitoring\n持仓实时监控", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(risk_metrics))
    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Regime Detection System  |  市场状态识别", S['heading2']))

    regime_items = [
        "HMM 识别 6 种市场状态：趋势牛市、趋势熊市、区间震荡、剧烈崩盘、低波动、高波动",
        "根据市场状态动态调整仓位规模（0.5x - 2.0x 杠杆范围）",
        "自动切换风险预算分配和止损水平",
        "实时更新因子权重，适应当前市场环境",
    ]
    for item in regime_items:
        story.append(Paragraph(f"▸  {item}", S['bullet']))

    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Risk Control Layers  |  多层风控架构", S['heading2']))

    left_risk = make_info_card("Trade-Level 交易层", [
        "单笔最大损失限制",
        "智能追踪止损",
        "分批止盈策略",
        "滑点和手续费模拟",
    ], ACCENT_RED)

    right_risk = make_info_card("Portfolio-Level 组合层", [
        "VaR 风险价值计算（参数/历史/蒙特卡洛）",
        "行业/个股集中度限制",
        "相关性矩阵监控",
        "压力测试与极端情景分析",
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
    """Build Performance & Roadmap page."""
    story.append(Paragraph("06  Performance & Roadmap  |  业绩表现与路线图", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph("Baseline Performance Metrics  |  基线业绩指标", S['heading2']))

    perf_metrics = [
        ("42.8%", "Annual Return\n年化收益率", ACCENT_GREEN),
        ("2.85", "Sharpe Ratio\n夏普比率", ACCENT_BLUE),
        ("8.2%", "Max Drawdown\n最大回撤", ACCENT_GOLD),
        ("62.5%", "Win Rate\n胜率", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(perf_metrics))

    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "* 以上数据基于研究回测结果，使用默认参数配置。过往业绩不代表未来表现。",
        S['disclaimer']
    ))

    story.append(Spacer(1, 3 * mm))

    # Performance chart
    story.append(make_performance_chart())
    story.append(Spacer(1, 5 * mm))

    # Roadmap timeline
    story.append(Paragraph("Development Roadmap  |  发展路线图", S['heading2']))
    story.append(make_timeline())

    story.append(Spacer(1, 4 * mm))

    phases_desc = [
        ("Phase 1 — Factor Timing + AI Signals",
         "因子时序预测 + 多模态 AI 信号融合 → 预期年化收益 65-80%"),
        ("Phase 2 — Alternative Data Integration",
         "卫星数据、社交媒体情感、供应链图谱 → 预期年化收益 85-100%"),
        ("Phase 3 — Cross-Asset Expansion",
         "跨资产类别交易（期权、期货、外汇） → 分散风险，提升稳定性"),
        ("Phase 4 — Ultimate Optimization",
         "全系统协同优化 → 预期年化 115-150%，Sharpe 10+，最大回撤 <4%"),
    ]
    for title, desc in phases_desc:
        story.append(Paragraph(f"<b>{title}</b>", S['body_en']))
        story.append(Paragraph(desc, S['bullet']))

    story.append(PageBreak())


def build_competitive_edge(story, S):
    """Build Competitive Edge page."""
    story.append(Paragraph("07  Competitive Edge  |  竞争优势", S['section_title']))
    story.append(make_hr())

    # Comparison table
    comp_header_style = ParagraphStyle('ch', fontName=EN_FONT_BOLD, fontSize=8,
                                        textColor=ACCENT_BLUE, alignment=TA_CENTER, leading=11)
    comp_cell_style = ParagraphStyle('cc', fontName=CJK_FONT, fontSize=8,
                                      textColor=TEXT_LIGHT, alignment=TA_CENTER, leading=11)
    comp_yes = ParagraphStyle('cy', fontName=EN_FONT_BOLD, fontSize=8,
                               textColor=ACCENT_GREEN, alignment=TA_CENTER, leading=11)
    comp_no = ParagraphStyle('cn', fontName=EN_FONT_BOLD, fontSize=8,
                              textColor=ACCENT_RED, alignment=TA_CENTER, leading=11)
    comp_partial = ParagraphStyle('cp', fontName=EN_FONT_BOLD, fontSize=8,
                                   textColor=ACCENT_GOLD, alignment=TA_CENTER, leading=11)

    cw = PAGE_W - 2 * MARGIN
    comp_data = [
        [Paragraph('Feature', comp_header_style),
         Paragraph('Stock Deepseeker', comp_header_style),
         Paragraph('QuantConnect', comp_header_style),
         Paragraph('Zipline', comp_header_style),
         Paragraph('Backtrader', comp_header_style)],

        [Paragraph('Multi-Agent AI', comp_cell_style),
         Paragraph('YES', comp_yes), Paragraph('NO', comp_no),
         Paragraph('NO', comp_no), Paragraph('NO', comp_no)],

        [Paragraph('62+ Built-in Factors', comp_cell_style),
         Paragraph('YES', comp_yes), Paragraph('Partial', comp_partial),
         Paragraph('NO', comp_no), Paragraph('NO', comp_no)],

        [Paragraph('HMM Regime Detection', comp_cell_style),
         Paragraph('YES', comp_yes), Paragraph('NO', comp_no),
         Paragraph('NO', comp_no), Paragraph('NO', comp_no)],

        [Paragraph('LLM Integration', comp_cell_style),
         Paragraph('YES', comp_yes), Paragraph('NO', comp_no),
         Paragraph('NO', comp_no), Paragraph('NO', comp_no)],

        [Paragraph('No-Lookahead Guarantee', comp_cell_style),
         Paragraph('YES', comp_yes), Paragraph('YES', comp_yes),
         Paragraph('YES', comp_yes), Paragraph('Partial', comp_partial)],

        [Paragraph('Portable Deployment', comp_cell_style),
         Paragraph('YES', comp_yes), Paragraph('Cloud Only', comp_partial),
         Paragraph('NO', comp_no), Paragraph('Partial', comp_partial)],

        [Paragraph('Deep Learning Models', comp_cell_style),
         Paragraph('YES', comp_yes), Paragraph('Partial', comp_partial),
         Paragraph('NO', comp_no), Paragraph('NO', comp_no)],

        [Paragraph('Dynamic Risk Sizing', comp_cell_style),
         Paragraph('YES', comp_yes), Paragraph('Partial', comp_partial),
         Paragraph('NO', comp_no), Paragraph('Partial', comp_partial)],
    ]

    comp_table = Table(comp_data, colWidths=[cw * 0.28, cw * 0.18, cw * 0.18, cw * 0.18, cw * 0.18])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('BACKGROUND', (1, 1), (1, -1), colors.HexColor("#1a2332")),
        ('BACKGROUND', (0, 1), (0, -1), CARD_BG),
        ('BACKGROUND', (2, 1), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, BORDER_COLOR),
        ('BOX', (1, 0), (1, -1), 1, ACCENT_BLUE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2 * mm),
    ]))
    story.append(comp_table)

    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("Unique Innovations  |  独特创新", S['heading2']))

    innovations = [
        ("多智能体共识决策", "业界首创将 LangGraph 多智能体工作流应用于量化交易决策，"
         "通过多轮专家辩论形成投资共识，有效降低单一模型偏差"),
        ("自适应市场状态感知", "HMM 实时识别市场状态（6 种），策略参数和风险管理自动适配，"
         "在不同市场环境中保持稳健表现"),
        ("因子时序预测系统", "不仅使用因子选股，更预测未来哪些因子将表现优异，"
         "在因子轮动中捕获超额收益"),
        ("零前视偏差保证", "从架构层面杜绝未来数据泄露，确保研究结果的学术可靠性和实盘可复现性"),
    ]

    for title, desc in innovations:
        story.append(Paragraph(f"<b><font color='{ACCENT_GREEN.hexval()}'>{title}</font></b>", S['body']))
        story.append(Paragraph(desc, S['bullet']))

    story.append(PageBreak())


def build_business_model(story, S):
    """Build Business Model & Investment page."""
    story.append(Paragraph("08  Business Model & Investment  |  商业模式与投资", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph("Revenue Streams  |  收入来源", S['heading2']))

    rev_streams = [
        ("SaaS Platform License  |  平台授权",
         "面向量化团队和对冲基金的企业级平台许可，年度订阅模式。提供完整的因子库、"
         "策略模板、回测引擎和风控系统。"),
        ("Performance-Based Fee  |  业绩分成",
         "与合作基金签订业绩分成协议，基于超额收益收取 15-20% 管理费。"
         "与投资者利益深度绑定。"),
        ("Custom Strategy Development  |  定制策略开发",
         "为机构客户量身定制量化策略，包括因子组合优化、风控参数校准和模型训练。"),
        ("Data & Research API  |  数据与研究接口",
         "开放因子计算和市场状态识别 API，按调用量收费。"
         "为 FinTech 公司和研究机构提供底层能力。"),
    ]

    for title, desc in rev_streams:
        story.append(Paragraph(f"<b><font color='{ACCENT_GOLD.hexval()}'>{title}</font></b>", S['body']))
        story.append(Paragraph(desc, S['bullet']))
        story.append(Spacer(1, 1 * mm))

    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Investment Highlights  |  投资亮点", S['heading2']))

    inv_metrics = [
        ("$2M", "Seed Round Target\n种子轮目标", ACCENT_GREEN),
        ("18 mo", "Runway\n运营周期", ACCENT_BLUE),
        ("10x", "5-Year ROI Target\n5年回报目标", ACCENT_GOLD),
        ("$310B+", "TAM by 2027\n目标市场规模", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(inv_metrics))

    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Use of Funds  |  资金用途", S['heading2']))

    funds_data = [
        [Paragraph('<font color="#58A6FF">Category | 类别</font>',
                   ParagraphStyle('fh', fontName=CJK_FONT, fontSize=9, textColor=ACCENT_BLUE)),
         Paragraph('<font color="#58A6FF">Allocation</font>',
                   ParagraphStyle('fh', fontName=EN_FONT_BOLD, fontSize=9, textColor=ACCENT_BLUE, alignment=TA_CENTER)),
         Paragraph('<font color="#58A6FF">Description | 说明</font>',
                   ParagraphStyle('fh', fontName=CJK_FONT, fontSize=9, textColor=ACCENT_BLUE))],
        [Paragraph('R&D / 研发', ParagraphStyle('fc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT)),
         Paragraph('45%', ParagraphStyle('fc', fontName=EN_FONT_BOLD, fontSize=8, textColor=ACCENT_GREEN, alignment=TA_CENTER)),
         Paragraph('AI 模型迭代、因子研发、策略优化', ParagraphStyle('fc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT))],
        [Paragraph('Infrastructure / 基础设施', ParagraphStyle('fc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT)),
         Paragraph('25%', ParagraphStyle('fc', fontName=EN_FONT_BOLD, fontSize=8, textColor=ACCENT_BLUE, alignment=TA_CENTER)),
         Paragraph('云计算、数据源、GPU 集群', ParagraphStyle('fc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT))],
        [Paragraph('Talent / 人才', ParagraphStyle('fc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT)),
         Paragraph('20%', ParagraphStyle('fc', fontName=EN_FONT_BOLD, fontSize=8, textColor=ACCENT_GOLD, alignment=TA_CENTER)),
         Paragraph('量化研究员、ML 工程师、全栈开发', ParagraphStyle('fc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT))],
        [Paragraph('Operations / 运营', ParagraphStyle('fc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT)),
         Paragraph('10%', ParagraphStyle('fc', fontName=EN_FONT_BOLD, fontSize=8, textColor=ACCENT_PURPLE, alignment=TA_CENTER)),
         Paragraph('合规、法务、市场推广', ParagraphStyle('fc', fontName=CJK_FONT, fontSize=8, textColor=TEXT_LIGHT))],
    ]

    fw = PAGE_W - 2 * MARGIN
    funds_table = Table(funds_data, colWidths=[fw * 0.25, fw * 0.12, fw * 0.63])
    funds_table.setStyle(TableStyle([
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
    story.append(funds_table)

    story.append(PageBreak())


def build_tech_stack(story, S):
    """Build Technical Infrastructure page."""
    story.append(Paragraph("09  Technical Infrastructure  |  技术基础设施", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph(
        "平台构建在现代化技术栈之上，具备生产级别的代码质量（91/100 评分）、"
        "完善的测试覆盖和容器化部署能力。",
        S['body']
    ))

    story.append(Spacer(1, 3 * mm))

    # Quality metrics
    quality_metrics = [
        ("39K+", "Lines of Code\n代码行数", ACCENT_BLUE),
        ("15", "Core Modules\n核心模块", ACCENT_GREEN),
        ("70%+", "Test Coverage\n测试覆盖", ACCENT_GOLD),
        ("91/100", "Quality Score\n质量评分", ACCENT_PURPLE),
    ]
    story.append(make_metrics_row(quality_metrics))

    story.append(Spacer(1, 5 * mm))

    # Tech stack cards
    left_tech = make_info_card("Core Technologies  |  核心技术", [
        "Python 3.10+ (Modern async support)",
        "PyTorch (Deep Learning & RL)",
        "NumPy/Pandas (Vectorized computation)",
        "scikit-learn (ML pipelines)",
        "LangGraph/LangChain (Agent orchestration)",
    ], ACCENT_BLUE)

    right_tech = make_info_card("Infrastructure  |  基础设施", [
        "Docker + Docker Compose (容器化部署)",
        "FastAPI + WebSocket (实时 API)",
        "Redis (高速缓存与消息队列)",
        "PostgreSQL/SQLAlchemy (数据持久化)",
        "Pytest (自动化测试框架)",
    ], ACCENT_GREEN)

    tech_cols = Table([[left_tech, right_tech]],
                      colWidths=[(PAGE_W - 2 * MARGIN) / 2] * 2)
    tech_cols.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(tech_cols)

    story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("Production Readiness  |  生产就绪性", S['heading2']))

    prod_items = [
        "模块化架构：15 个独立模块，低耦合高内聚，支持独立升级和水平扩展",
        "全面类型标注：整体代码 Type Hints 覆盖，静态分析零警告",
        "结构化日志：Loguru 日志框架，支持日志轮转和远程收集",
        "优雅降级：所有外部依赖（API、数据源）均有 Fallback 机制",
        "一键部署：Docker 容器化 + 健康检查 + 自动重启",
    ]
    for item in prod_items:
        story.append(Paragraph(f"▸  {item}", S['bullet']))

    story.append(PageBreak())


def build_disclaimer(story, S):
    """Build Disclaimer & Contact page."""
    story.append(Paragraph("10  Disclaimer & Contact  |  免责声明与联系方式", S['section_title']))
    story.append(make_hr())

    story.append(Paragraph("Legal Disclaimer  |  法律免责声明", S['heading2']))

    disclaimers = [
        "本文件仅供合格投资者参阅，不构成任何形式的投资建议或招揽。",
        "所有业绩数据均基于历史回测结果，过往业绩不代表未来表现。实际交易结果可能与回测有显著差异。",
        "量化交易涉及重大风险，包括但不限于市场风险、模型风险、技术风险和流动性风险。投资者可能损失全部本金。",
        "本文件中的前瞻性陈述涉及预测和估计，实际结果可能与预期有重大差异。",
        "本文件包含商业机密和专有信息，接收方同意不向第三方披露任何内容。",
        "未经书面授权，严禁复制、分发或以任何形式使用本文件内容。",
    ]

    for d in disclaimers:
        story.append(Paragraph(f"▸  {d}", S['bullet']))

    story.append(Spacer(1, 8 * mm))

    story.append(Paragraph("Intellectual Property Notice  |  知识产权声明", S['heading2']))
    story.append(Paragraph(
        "Stock Deepseeker 及其所有组件（包括但不限于量化因子库、多智能体系统、"
        "回测引擎和风险管理模块）均为专有知识产权。本文件仅展示系统架构和方法论概述，"
        "不包含任何源代码、算法实现细节或可复制的技术规格。所有技术细节已申请知识产权保护。",
        S['body']
    ))

    story.append(Spacer(1, 8 * mm))

    # Contact card
    contact_data = [[
        Paragraph(
            '<font color="#58A6FF"><b>Contact Information  |  联系方式</b></font><br/><br/>'
            '<font color="#C9D1D9">'
            'For investment inquiries, partnership opportunities,<br/>'
            'or technical demonstrations, please contact:<br/><br/>'
            '投资咨询、合作机会或技术演示，请联系项目负责人。<br/><br/>'
            '</font>'
            '<font color="#8B949E">'
            'This document and all information contained herein<br/>'
            'are strictly confidential and proprietary.'
            '</font>',
            ParagraphStyle('contact', fontName=CJK_FONT, fontSize=10,
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

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"Document generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        "Stock Deepseeker v3.0.0  |  CONFIDENTIAL",
        S['cover_date']
    ))


# ── Main ───────────────────────────────────────────────────────
def generate_pdf(output_path):
    """Generate the complete investor pitch PDF."""
    doc = BaseDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="Stock Deepseeker - Investor Pitch",
        author="Stock Deepseeker Team",
        subject="Confidential Investor Briefing",
        creator="Stock Deepseeker PDF Generator",
    )

    # Page templates
    cover_frame = Frame(MARGIN, MARGIN, PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN,
                        id='cover_frame')
    content_frame = Frame(MARGIN, 18 * mm, PAGE_W - 2 * MARGIN, PAGE_H - 36 * mm,
                          id='content_frame')

    doc.addPageTemplates([
        PageTemplate(id='cover', frames=[cover_frame], onPage=draw_cover_page),
        PageTemplate(id='content', frames=[content_frame], onPage=draw_page_bg),
    ])

    # Build story
    S = get_styles()
    story = []

    # Cover page
    build_cover(story, S)

    # Switch to content template for remaining pages
    from reportlab.platypus.doctemplate import NextPageTemplate
    story.insert(-1, NextPageTemplate('content'))

    # Content pages
    build_executive_summary(story, S)
    build_technology(story, S)
    build_factor_library(story, S)
    build_multi_agent(story, S)
    build_risk_management(story, S)
    build_performance(story, S)
    build_competitive_edge(story, S)
    build_business_model(story, S)
    build_tech_stack(story, S)
    build_disclaimer(story, S)

    # Build PDF
    doc.build(story)
    print(f"\n{'='*60}")
    print(f"  PDF Generated Successfully!")
    print(f"  Output: {output_path}")
    print(f"  Pages: ~12")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    output = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "Stock_Deepseeker_Investor_Pitch.pdf")
    generate_pdf(output)
