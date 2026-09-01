from __future__ import annotations

from collections.abc import Iterable
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from anton.schemas import Account, AccountSynthesis, PostFinding

INK = colors.HexColor("#171719")
CREAM = colors.HexColor("#F7F3EA")
RED = colors.HexColor("#F54635")
YELLOW = colors.HexColor("#F7D866")
MINT = colors.HexColor("#CDE3D1")
BLUE = colors.HexColor("#C8D9EA")
WHITE = colors.white
MUTED = colors.HexColor("#66635E")
LINE = colors.HexColor("#D4CDC1")


def _register_fonts() -> None:
    import reportlab

    font_dir = Path(reportlab.__file__).parent / "fonts"
    pdfmetrics.registerFont(TTFont("AntonSans", str(font_dir / "Vera.ttf")))
    pdfmetrics.registerFont(TTFont("AntonSans-Bold", str(font_dir / "VeraBd.ttf")))
    addMapping("AntonSans", 0, 0, "AntonSans")
    addMapping("AntonSans", 1, 0, "AntonSans-Bold")


_register_fonts()

COPY = {
    "en": {
        "report": "CREATOR GROWTH AUDIT",
        "cover_line_1": "CLEAR SIGNALS.",
        "cover_line_2": "BETTER CONTENT.",
        "cover_line_3": "A PLAN TO TEST.",
        "cover_note": (
            "A focused account audit that turns recent content and performance into a "
            "practical plan."
        ),
        "short": "THE SHORT VERSION",
        "short_title": "The clearest opportunity in your content.",
        "short_intro": (
            "What the available content and performance signals say - without the noise."
        ),
        "big_idea": "THE BIG IDEA",
        "decision": "THE DECISION",
        "keep": "KEEP",
        "change": "SHARPEN",
        "test": "TEST NEXT",
        "snapshot": "PERFORMANCE SNAPSHOT",
        "snapshot_title": "The numbers behind the direction.",
        "snapshot_intro": (
            "A compact view of scale, response and data coverage across the posts reviewed."
        ),
        "followers": "FOLLOWERS",
        "posts": "POSTS REVIEWED",
        "total_reach": "TOTAL REACH",
        "interactions": "TOTAL INTERACTIONS",
        "median_reach_card": "MEDIAN REACH",
        "median_interactions_card": "MEDIAN INTERACTIONS",
        "coverage": "FORMAT BREAKDOWN",
        "format": "FORMAT",
        "top": "TOP CONTENT",
        "top_title": "The posts that best explain what works.",
        "top_intro": "These pieces combine the strongest available interaction and reach signals.",
        "formats": "FORMAT + CONTENT STRATEGY",
        "formats_title": "Give every recurring format a clear job.",
        "formats_intro": "Use performance patterns to decide what each format should achieve.",
        "pillars": "REPEATABLE CONTENT PILLARS",
        "visual": "VISUAL DIRECTION",
        "visual_title": "Build recognition before someone reads the caption.",
        "visual_intro": (
            "The recurring visual cues and audience-response patterns worth making intentional."
        ),
        "signals": "AUDIENCE RESPONSE SIGNALS",
        "actions": "KEEP / SHARPEN / TEST",
        "actions_title": "Protect what works. Fix what slows it down.",
        "actions_intro": (
            "The next month should improve clarity and repeatability, not add random formats."
        ),
        "focus": "30-DAY FOCUS",
        "plan": "30-DAY PLAN",
        "plan_title": "Four weeks with a clear purpose.",
        "plan_intro": (
            "One focused move per week, designed to create evidence you can use next month."
        ),
        "measure": "MEASUREMENT PLAN",
        "measure_title": "Know what changed - and why.",
        "measure_intro": (
            "Review the same small set of signals every week instead of chasing every number."
        ),
        "reach": "REACH",
        "reach_note": "Discovery: unique accounts that saw the content.",
        "saves": "SAVES",
        "saves_note": "Utility: whether the content was worth returning to.",
        "shares": "SHARES",
        "shares_note": "Relevance: whether it was worth sending onward.",
        "rate": "ACTIONS / REACH",
        "rate_note": "Average response actions compared with accounts reached.",
        "routine": "WEEKLY REVIEW ROUTINE",
        "limitations": "READ THIS REPORT WITH CONTEXT",
        "no_metric": "N/A",
        "pieces": "pieces",
        "median_reach": "median reach",
        "median_interactions": "median interactions",
        "interaction_rate": "actions / reach",
        "account_size": "Account size",
        "included": "Included in this audit",
        "posts_with_reach": "posts with reach data",
        "median_rate_note": "median actions / reach",
        "format_signal": "FORMAT SIGNAL",
        "week": "WEEK",
        "top_reach": "Reach",
        "top_interactions": "Interactions",
        "top_saves": "Saves",
        "top_views": "Views",
        "data_coverage": "DATA COVERAGE",
        "data_window": "DATE RANGE",
        "reach_coverage": "REACH COVERAGE",
        "depth_coverage": "DEEP ACTION COVERAGE",
        "posts_label": "posts",
        "with_reach": "include reach",
        "with_saves": "include saves",
        "with_shares": "include shares",
    },
    "es": {
        "report": "AUDITORÍA DE CRECIMIENTO",
        "cover_line_1": "SEÑALES CLARAS.",
        "cover_line_2": "MEJOR CONTENIDO.",
        "cover_line_3": "UN PLAN PARA PROBAR.",
        "cover_note": (
            "Una auditoría enfocada que convierte el contenido y rendimiento recientes en un "
            "plan práctico."
        ),
        "short": "LA VERSIÓN CORTA",
        "short_title": "La oportunidad más clara de tu contenido.",
        "short_intro": (
            "Lo que dicen las señales disponibles de contenido y rendimiento, sin ruido."
        ),
        "big_idea": "LA GRAN IDEA",
        "decision": "LA DECISIÓN",
        "keep": "MANTÉN",
        "change": "PULIR",
        "test": "PRUEBA",
        "snapshot": "PANORAMA DE RENDIMIENTO",
        "snapshot_title": "Los números detrás de la dirección.",
        "snapshot_intro": (
            "Una vista compacta de escala, respuesta y cobertura de los posts revisados."
        ),
        "followers": "SEGUIDORES",
        "posts": "PIEZAS REVISADAS",
        "total_reach": "ALCANCE TOTAL",
        "interactions": "INTERACCIONES TOTALES",
        "median_reach_card": "ALCANCE MEDIANO",
        "median_interactions_card": "INTERACCIONES MEDIANAS",
        "coverage": "DESGLOSE POR FORMATO",
        "format": "FORMATO",
        "top": "MEJOR CONTENIDO",
        "top_title": "Los posts que mejor explican qué funciona.",
        "top_intro": (
            "Estas piezas combinan las señales disponibles más fuertes de interacción y alcance."
        ),
        "formats": "ESTRATEGIA DE FORMATOS Y CONTENIDO",
        "formats_title": "Dale un trabajo claro a cada formato recurrente.",
        "formats_intro": (
            "Usa los patrones de rendimiento para decidir qué debe lograr cada formato."
        ),
        "pillars": "PILARES DE CONTENIDO REPETIBLES",
        "visual": "DIRECCIÓN VISUAL",
        "visual_title": "Construye reconocimiento antes de que lean el caption.",
        "visual_intro": (
            "Las señales visuales y patrones de respuesta que conviene volver intencionales."
        ),
        "signals": "SEÑALES DE RESPUESTA",
        "actions": "MANTENER / PULIR / PROBAR",
        "actions_title": "Protege lo que funciona. Corrige lo que frena.",
        "actions_intro": (
            "El próximo mes debe mejorar claridad y repetición, no sumar formatos al azar."
        ),
        "focus": "FOCO DE 30 DÍAS",
        "plan": "PLAN DE 30 DÍAS",
        "plan_title": "Cuatro semanas con un propósito claro.",
        "plan_intro": (
            "Un movimiento enfocado por semana para crear evidencia útil para el próximo mes."
        ),
        "measure": "PLAN DE MEDICIÓN",
        "measure_title": "Sabe qué cambió y por qué.",
        "measure_intro": (
            "Revisa cada semana las mismas señales clave, en lugar de perseguir cada número."
        ),
        "reach": "ALCANCE",
        "reach_note": "Descubrimiento: cuentas únicas que vieron el contenido.",
        "saves": "GUARDADOS",
        "saves_note": "Utilidad: si valió la pena volver al contenido.",
        "shares": "COMPARTIDOS",
        "shares_note": "Relevancia: si valió la pena enviarlo a alguien.",
        "rate": "ACCIONES / ALCANCE",
        "rate_note": "Promedio de acciones frente a las cuentas alcanzadas.",
        "routine": "RUTINA DE REVISIÓN SEMANAL",
        "limitations": "LEE ESTE REPORTE CON CONTEXTO",
        "no_metric": "N/D",
        "pieces": "piezas",
        "median_reach": "alcance mediano",
        "median_interactions": "interacciones medianas",
        "interaction_rate": "acciones / alcance",
        "account_size": "Tamaño de la cuenta",
        "included": "Incluidas en esta auditoría",
        "posts_with_reach": "posts con datos de alcance",
        "median_rate_note": "mediana de acciones / alcance",
        "format_signal": "SEÑAL DE FORMATO",
        "week": "SEMANA",
        "top_reach": "Alcance",
        "top_interactions": "Interacciones",
        "top_saves": "Guardados",
        "top_views": "Visualizaciones",
        "data_coverage": "COBERTURA DE DATOS",
        "data_window": "PERIODO",
        "reach_coverage": "COBERTURA DE ALCANCE",
        "depth_coverage": "COBERTURA DE ACCIONES",
        "posts_label": "posts",
        "with_reach": "incluyen alcance",
        "with_saves": "incluyen guardados",
        "with_shares": "incluyen compartidos",
    },
}


class Rule(Flowable):
    def __init__(self, width: float, color=LINE, thickness: float = 1) -> None:
        super().__init__()
        self.width = width
        self.height = thickness
        self.color = color
        self.thickness = thickness

    def draw(self) -> None:
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(self.thickness)
        self.canv.line(0, 0, self.width, 0)


class CropImage(Flowable):
    def __init__(self, path: str | Path, width: float, height: float) -> None:
        super().__init__()
        self.path = str(path)
        self.width = width
        self.height = height

    def draw(self) -> None:
        reader = ImageReader(self.path)
        source_width, source_height = reader.getSize()
        scale = max(self.width / source_width, self.height / source_height)
        draw_width = source_width * scale
        draw_height = source_height * scale
        self.canv.saveState()
        clip = self.canv.beginPath()
        clip.rect(0, 0, self.width, self.height)
        self.canv.clipPath(clip, stroke=0, fill=0)
        self.canv.drawImage(
            reader,
            (self.width - draw_width) / 2,
            (self.height - draw_height) / 2,
            draw_width,
            draw_height,
            mask="auto",
        )
        self.canv.restoreState()


class CoverPage(Flowable):
    def __init__(
        self,
        brand_name: str,
        account: Account,
        positioning: str,
        image_paths: list[str],
        copy: dict[str, str],
        styles: dict[str, ParagraphStyle],
    ) -> None:
        super().__init__()
        self.width, self.height = A4
        self.brand_name = brand_name
        self.account = account
        self.positioning = positioning
        self.image_paths = image_paths
        self.copy = copy
        self.styles = styles

    def _paragraph(
        self, text: str, style: ParagraphStyle, x: float, y: float, width: float
    ) -> None:
        paragraph = Paragraph(escape(text), style)
        _, height = paragraph.wrap(width, self.height)
        paragraph.drawOn(self.canv, x, y - height)

    def draw(self) -> None:
        page_width, page_height = A4
        rail_width = 64 * mm
        self.canv.setFillColor(CREAM)
        self.canv.rect(0, 0, page_width, page_height, fill=1, stroke=0)
        self.canv.setFillColor(RED)
        self.canv.rect(0, 0, rail_width, page_height, fill=1, stroke=0)

        self.canv.setFillColor(INK)
        self.canv.setFont("AntonSans-Bold", 10)
        self.canv.drawString(75 * mm, page_height - 26 * mm, self.brand_name.upper())
        self.canv.setFillColor(RED)
        self.canv.setFont("AntonSans-Bold", 8)
        self.canv.drawString(75 * mm, page_height - 35 * mm, self.copy["report"])
        self.canv.setFillColor(INK)
        self.canv.setFont("AntonSans-Bold", 18)
        self.canv.drawString(75 * mm, page_height - 50 * mm, f"@{self.account.username}")

        grid_x = 75 * mm
        grid_y = 97 * mm
        gap = 4 * mm
        cell_width = 52 * mm
        cell_height = 52 * mm
        fallback_colors = [YELLOW, MINT, BLUE, WHITE]
        for index in range(4):
            x = grid_x + (index % 2) * (cell_width + gap)
            y = grid_y + (1 - index // 2) * (cell_height + gap)
            if index < len(self.image_paths):
                image = CropImage(self.image_paths[index], cell_width, cell_height)
                image.canv = self.canv
                self.canv.saveState()
                self.canv.translate(x, y)
                image.draw()
                self.canv.restoreState()
            else:
                self.canv.setFillColor(fallback_colors[index])
                self.canv.rect(x, y, cell_width, cell_height, fill=1, stroke=0)

        self._paragraph(
            _shorten(self.positioning, 210),
            self.styles["cover_positioning"],
            grid_x,
            82 * mm,
            108 * mm,
        )
        self._paragraph(
            self.copy["cover_note"], self.styles["cover_small"], grid_x, 34 * mm, 108 * mm
        )

        rail_copy = "<br/>".join(
            [self.copy["cover_line_1"], self.copy["cover_line_2"], self.copy["cover_line_3"]]
        )
        paragraph = Paragraph(rail_copy, self.styles["cover_rail"])
        _, paragraph_height = paragraph.wrap(50 * mm, 100 * mm)
        paragraph.drawOn(self.canv, 8 * mm, 34 * mm + paragraph_height)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=7.5,
            leading=9,
            textColor=RED,
            spaceAfter=8,
        ),
        "hero": ParagraphStyle(
            "Hero",
            parent=base["Title"],
            fontName="AntonSans-Bold",
            fontSize=27,
            leading=30,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=10.5,
            leading=15,
            textColor=INK,
            spaceAfter=12,
        ),
        "subtitle_white": ParagraphStyle(
            "SubtitleWhite",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=10.5,
            leading=15,
            textColor=WHITE,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="AntonSans-Bold",
            fontSize=16,
            leading=19,
            textColor=INK,
            spaceBefore=6,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="AntonSans",
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
            spaceAfter=5,
        ),
        "body_bold": ParagraphStyle(
            "BodyBold",
            parent=base["BodyText"],
            fontName="AntonSans-Bold",
            fontSize=9.2,
            leading=13.2,
            textColor=INK,
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="AntonSans",
            fontSize=7.3,
            leading=10,
            textColor=MUTED,
        ),
        "card_title": ParagraphStyle(
            "CardTitle",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=9.3,
            leading=12,
            textColor=INK,
            spaceAfter=6,
        ),
        "card_body": ParagraphStyle(
            "CardBody",
            parent=base["BodyText"],
            fontName="AntonSans",
            fontSize=8.2,
            leading=11.5,
            textColor=INK,
            spaceAfter=4,
        ),
        "metric": ParagraphStyle(
            "Metric",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=20,
            leading=22,
            textColor=INK,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=6.8,
            leading=8,
            textColor=INK,
        ),
        "metric_label_white": ParagraphStyle(
            "MetricLabelWhite",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=6.8,
            leading=8,
            textColor=WHITE,
        ),
        "metric_note": ParagraphStyle(
            "MetricNote",
            parent=base["Normal"],
            fontName="AntonSans",
            fontSize=7,
            leading=8.7,
            textColor=INK,
        ),
        "cover_positioning": ParagraphStyle(
            "CoverPositioning",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=10.5,
            leading=15,
            textColor=INK,
        ),
        "cover_small": ParagraphStyle(
            "CoverSmall",
            parent=base["Normal"],
            fontName="AntonSans",
            fontSize=7.5,
            leading=10,
            textColor=INK,
        ),
        "cover_rail": ParagraphStyle(
            "CoverRail",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=19,
            leading=24,
            textColor=INK,
        ),
    }


def _shorten(value: str | None, limit: int) -> str:
    if not value:
        return ""
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 1].rsplit(" ", 1)[0] + "…"


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def _format_number(value: int | float | None, missing: str) -> str:
    if value is None:
        return missing
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def _format_percent(value: int | float | None, missing: str) -> str:
    return missing if value is None else f"{value:.1f}%"


def _bullet_list(
    items: Iterable[str], style: ParagraphStyle, *, limit: int = 4, char_limit: int = 180
) -> list[Flowable]:
    output: list[Flowable] = []
    bullet_style = ParagraphStyle(
        f"{style.name}Bullet", parent=style, leftIndent=9, firstLineIndent=-8, bulletIndent=0
    )
    for item in list(items)[:limit]:
        output.append(Paragraph(escape(_shorten(item, char_limit)), bullet_style, bulletText="+"))
    return output


def _page_intro(
    copy: dict[str, str], eyebrow: str, title: str, intro: str, styles: dict, width: float
) -> list[Flowable]:
    return [
        _p(copy[eyebrow], styles["eyebrow"]),
        _p(copy[title], styles["hero"]),
        Rule(width),
        Spacer(1, 6 * mm),
        _p(copy[intro], styles["subtitle"]),
        Spacer(1, 4 * mm),
    ]


def _metric_card(
    label: str, value: str, note: str, background, styles: dict, width: float = 39 * mm
) -> Table:
    card = Table(
        [
            [_p(value, styles["metric"])],
            [_p(label, styles["metric_label"])],
            [_p(note, styles["metric_note"])],
        ],
        colWidths=[width],
        rowHeights=[13 * mm, 7 * mm, 12 * mm],
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 2 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * mm),
            ]
        )
    )
    return card


def _signal_card(label: str, text: str, background, styles: dict) -> Table:
    card = Table(
        [[_p(label, styles["card_title"])], [_p(_shorten(text, 190), styles["card_body"])]],
        colWidths=[51 * mm],
        rowHeights=[12 * mm, 34 * mm],
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]
        )
    )
    return card


def _action_card(title: str, items: list[str], background, styles: dict) -> Table:
    content: list[Flowable] = [
        _p(title, styles["section"]),
        Rule(42 * mm, INK, 0.8),
        Spacer(1, 5 * mm),
    ]
    content.extend(_bullet_list(items, styles["card_body"], limit=4, char_limit=115))
    table = Table([[content]], colWidths=[51 * mm], rowHeights=[142 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 6 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
            ]
        )
    )
    return table


def _top_post_card(
    finding: PostFinding,
    rank: int,
    styles: dict,
    copy: dict[str, str],
) -> Table:
    if finding.thumbnail_path and Path(finding.thumbnail_path).exists():
        image: Flowable = CropImage(finding.thumbnail_path, 48 * mm, 48 * mm)
    else:
        image = Table(
            [[_p(f"{rank:02d}", styles["metric"])]], colWidths=[48 * mm], rowHeights=[48 * mm]
        )
        image.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), YELLOW),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

    metrics = finding.metrics
    metric_bits = [
        f"{copy['top_reach']} {_format_number(metrics.get('reach'), copy['no_metric'])}",
        (
            f"{copy['top_interactions']} "
            f"{_format_number(metrics.get('total_interactions'), copy['no_metric'])}"
        ),
    ]
    if metrics.get("saved") is not None:
        metric_bits.append(
            f"{copy['top_saves']} {_format_number(metrics.get('saved'), copy['no_metric'])}"
        )
    elif metrics.get("views") is not None:
        metric_bits.append(
            f"{copy['top_views']} {_format_number(metrics.get('views'), copy['no_metric'])}"
        )
    details = [
        _p(f"{rank:02d}  {finding.media_type.replace('_', ' ').upper()}", styles["eyebrow"]),
        _p(_shorten(finding.visual.summary, 190), styles["card_body"]),
        Spacer(1, 2 * mm),
        _p(
            "  ·  ".join(metric_bits),
            styles["small"],
        ),
    ]
    table = Table([[image, details]], colWidths=[48 * mm, 112 * mm], rowHeights=[48 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), 0),
                ("TOPPADDING", (0, 0), (0, 0), 0),
                ("BOTTOMPADDING", (0, 0), (0, 0), 0),
                ("LEFTPADDING", (1, 0), (1, 0), 6 * mm),
                ("RIGHTPADDING", (1, 0), (1, 0), 6 * mm),
            ]
        )
    )
    return table


def _week_row(index: int, text: str, background, styles: dict, copy: dict[str, str]) -> Table:
    row = Table(
        [
            [
                _p(f"{copy['week']} {index}", styles["metric_label"]),
                _p(_shorten(text, 260), styles["body_bold"]),
            ]
        ],
        colWidths=[36 * mm, 124 * mm],
        rowHeights=[31 * mm],
    )
    row.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), background),
                ("BACKGROUND", (1, 0), (1, 0), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
            ]
        )
    )
    return row


def _format_rows(aggregates: dict, copy: dict[str, str], styles: dict) -> list[list[Flowable]]:
    rows: list[list[Flowable]] = [
        [
            _p(copy["format"], styles["metric_label_white"]),
            _p(copy["pieces"].upper(), styles["metric_label_white"]),
            _p(copy["median_reach"].upper(), styles["metric_label_white"]),
            _p(copy["median_interactions"].upper(), styles["metric_label_white"]),
            _p(copy["interaction_rate"].upper(), styles["metric_label_white"]),
        ]
    ]
    format_metrics = aggregates.get("format_metrics") or {
        media_type: {"count": count}
        for media_type, count in (aggregates.get("formats") or {}).items()
    }
    for media_type, metrics in list(format_metrics.items())[:4]:
        rows.append(
            [
                _p(media_type.replace("_", " ").title(), styles["body_bold"]),
                _p(str(metrics.get("count", 0)), styles["body"]),
                _p(_format_number(metrics.get("median_reach"), copy["no_metric"]), styles["body"]),
                _p(
                    _format_number(metrics.get("median_interactions"), copy["no_metric"]),
                    styles["body"],
                ),
                _p(
                    _format_percent(metrics.get("median_interaction_rate"), copy["no_metric"]),
                    styles["body"],
                ),
            ]
        )
    return rows


def _dark_callout(text: str, styles: dict) -> Table:
    box = Table([[_p(_shorten(text, 220), styles["subtitle_white"])]], colWidths=[160 * mm])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), INK),
                ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 6 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
            ]
        )
    )
    return box


def build_report(
    output_path: Path,
    brand_name: str,
    language: str,
    account: Account,
    synthesis: AccountSynthesis,
    findings: list[PostFinding],
    aggregates: dict,
) -> Path:
    copy = COPY[language]
    styles = _styles()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    document = BaseDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{brand_name} - @{account.username}",
        author=brand_name,
    )
    cover_frame = Frame(
        0,
        0,
        A4[0],
        A4[1],
        id="cover",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )
    report_frame = Frame(
        document.leftMargin,
        document.bottomMargin,
        document.width,
        document.height,
        id="report",
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
    )

    def decorate(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(CREAM)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setStrokeColor(LINE)
        canvas.line(22 * mm, 13 * mm, A4[0] - 22 * mm, 13 * mm)
        canvas.setFillColor(INK)
        canvas.setFont("AntonSans-Bold", 6.5)
        canvas.drawString(22 * mm, 8 * mm, f"{brand_name.upper()} / @{account.username.upper()}")
        canvas.drawRightString(A4[0] - 22 * mm, 8 * mm, f"{doc.page:02d}")
        canvas.restoreState()

    document.addPageTemplates(
        [
            PageTemplate(id="cover", frames=[cover_frame]),
            PageTemplate(id="report", frames=[report_frame], onPage=decorate),
        ]
    )

    ranked = sorted(
        findings,
        key=lambda item: (
            item.metrics.get("total_interactions") or 0,
            item.metrics.get("reach") or 0,
        ),
        reverse=True,
    )
    image_paths = [
        finding.thumbnail_path
        for finding in ranked
        if finding.thumbnail_path and Path(finding.thumbnail_path).exists()
    ][:4]

    story: list[Flowable] = [
        CoverPage(brand_name, account, synthesis.account_positioning, image_paths, copy, styles),
        NextPageTemplate("report"),
        PageBreak(),
    ]

    story.extend(_page_intro(copy, "short", "short_title", "short_intro", styles, document.width))
    story.extend(_bullet_list(synthesis.executive_summary, styles["body"], limit=4, char_limit=180))
    story.extend([Spacer(1, 5 * mm), _p(copy["big_idea"], styles["eyebrow"])])
    big_idea = (
        synthesis.executive_summary[0]
        if synthesis.executive_summary
        else synthesis.account_positioning
    )
    story.extend([_dark_callout(big_idea, styles), Spacer(1, 7 * mm)])
    story.append(
        Table(
            [
                [
                    _signal_card(copy["keep"], (synthesis.keep or [""])[0], RED, styles),
                    _signal_card(copy["change"], (synthesis.change or [""])[0], YELLOW, styles),
                    _signal_card(copy["test"], (synthesis.tests or [""])[0], MINT, styles),
                ]
            ],
            colWidths=[53 * mm] * 3,
            hAlign="LEFT",
        )
    )
    story.extend([Spacer(1, 8 * mm), _p(copy["decision"], styles["eyebrow"])])
    decision = (synthesis.change or synthesis.tests or synthesis.executive_summary)[0]
    story.extend([_p(_shorten(decision, 220), styles["section"]), PageBreak()])

    story.extend(
        _page_intro(copy, "snapshot", "snapshot_title", "snapshot_intro", styles, document.width)
    )
    total_reach = aggregates.get("total_reach")
    total_interactions = aggregates.get("total_interactions")
    cards = [
        _metric_card(
            copy["followers"],
            _format_number(account.followers_count, copy["no_metric"]),
            copy["account_size"],
            RED,
            styles,
        ),
        _metric_card(
            copy["posts"],
            _format_number(aggregates.get("analyzed_posts"), copy["no_metric"]),
            copy["included"],
            YELLOW,
            styles,
        ),
        _metric_card(
            copy["total_reach"] if total_reach is not None else copy["median_reach_card"],
            _format_number(
                total_reach if total_reach is not None else aggregates.get("median_reach"),
                copy["no_metric"],
            ),
            f"{aggregates.get('posts_with_reach', 0)} {copy['posts_with_reach']}",
            MINT,
            styles,
        ),
        _metric_card(
            (
                copy["interactions"]
                if total_interactions is not None
                else copy["median_interactions_card"]
            ),
            _format_number(
                total_interactions
                if total_interactions is not None
                else aggregates.get("median_interactions"),
                copy["no_metric"],
            ),
            _format_percent(aggregates.get("median_interaction_rate"), copy["no_metric"])
            + f" {copy['median_rate_note']}",
            BLUE,
            styles,
        ),
    ]
    story.extend([Table([cards], colWidths=[40 * mm] * 4, hAlign="LEFT"), Spacer(1, 8 * mm)])
    format_table = Table(
        _format_rows(aggregates, copy, styles),
        colWidths=[42 * mm, 20 * mm, 34 * mm, 36 * mm, 30 * mm],
        repeatRows=1,
    )
    format_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("BACKGROUND", (0, 1), (-1, -1), WHITE),
                ("GRID", (0, 0), (-1, -1), 0.6, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
            ]
        )
    )
    analyzed_posts = aggregates.get("analyzed_posts") or 0
    date_from = (aggregates.get("date_from") or copy["no_metric"])[:10]
    date_to = (aggregates.get("date_to") or copy["no_metric"])[:10]
    coverage_cards = [
        _signal_card(
            copy["data_window"],
            f"{date_from} — {date_to}",
            WHITE,
            styles,
        ),
        _signal_card(
            copy["reach_coverage"],
            (
                f"{aggregates.get('posts_with_reach', 0)} / {analyzed_posts} "
                f"{copy['posts_label']} {copy['with_reach']}."
            ),
            MINT,
            styles,
        ),
        _signal_card(
            copy["depth_coverage"],
            (
                f"{aggregates.get('posts_with_saves', 0)} / {analyzed_posts} "
                f"{copy['with_saves']} · {aggregates.get('posts_with_shares', 0)} / "
                f"{analyzed_posts} {copy['with_shares']}."
            ),
            BLUE,
            styles,
        ),
    ]
    story.extend(
        [
            _p(copy["coverage"], styles["eyebrow"]),
            format_table,
            Spacer(1, 8 * mm),
            _p(copy["data_coverage"], styles["eyebrow"]),
            Table([coverage_cards], colWidths=[53 * mm] * 3, hAlign="LEFT"),
            PageBreak(),
        ]
    )

    story.extend(_page_intro(copy, "top", "top_title", "top_intro", styles, document.width))
    for index, finding in enumerate(ranked[:3], 1):
        story.extend(
            [
                KeepTogether(_top_post_card(finding, index, styles, copy)),
                Spacer(1, 5 * mm),
            ]
        )
    story.append(PageBreak())

    story.extend(
        _page_intro(copy, "formats", "formats_title", "formats_intro", styles, document.width)
    )
    format_cards = []
    for media_type, metrics in list((aggregates.get("format_metrics") or {}).items())[:3]:
        description = (
            f"{metrics.get('count', 0)} {copy['pieces']} · "
            f"{_format_number(metrics.get('median_reach'), copy['no_metric'])} "
            f"{copy['median_reach']} · "
            f"{_format_percent(metrics.get('median_interaction_rate'), copy['no_metric'])} "
            f"{copy['interaction_rate']}"
        )
        format_cards.append(
            _signal_card(media_type.replace("_", " ").upper(), description, WHITE, styles)
        )
    fallback_patterns = synthesis.format_patterns or synthesis.content_pillars or [""]
    while len(format_cards) < 3:
        format_cards.append(
            _signal_card(
                copy["format_signal"],
                fallback_patterns[len(format_cards) % len(fallback_patterns)],
                WHITE,
                styles,
            )
        )
    story.extend(
        [
            Table([format_cards], colWidths=[53 * mm] * 3, hAlign="LEFT"),
            Spacer(1, 10 * mm),
            _p(copy["pillars"], styles["eyebrow"]),
        ]
    )
    pillar_rows = []
    colors_cycle = [RED, YELLOW, MINT, BLUE]
    pillars = synthesis.content_pillars or synthesis.format_patterns
    for index, pillar in enumerate(pillars[:4], 1):
        number = Table(
            [[_p(f"{index:02d}", styles["metric_label"])]],
            colWidths=[18 * mm],
            rowHeights=[18 * mm],
        )
        number.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors_cycle[index - 1]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        pillar_rows.append([number, _p(_shorten(pillar, 180), styles["body_bold"])])
    pillars_table = Table(
        pillar_rows, colWidths=[22 * mm, 138 * mm], rowHeights=[21 * mm] * len(pillar_rows)
    )
    pillars_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
                ("BACKGROUND", (1, 0), (1, -1), WHITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (1, 0), (1, -1), 5 * mm),
            ]
        )
    )
    story.extend([pillars_table, PageBreak()])

    story.extend(
        _page_intro(copy, "visual", "visual_title", "visual_intro", styles, document.width)
    )
    visual_images: list[Flowable] = [CropImage(path, 52 * mm, 45 * mm) for path in image_paths[:3]]
    while len(visual_images) < 3:
        placeholder = Table(
            [[_p("VISUAL", styles["metric_label"])]], colWidths=[52 * mm], rowHeights=[45 * mm]
        )
        placeholder.setStyle(
            TableStyle(
                [("BACKGROUND", (0, 0), (-1, -1), YELLOW), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
            )
        )
        visual_images.append(placeholder)
    story.extend(
        [Table([visual_images], colWidths=[54 * mm] * 3, hAlign="LEFT"), Spacer(1, 8 * mm)]
    )
    two_columns = Table(
        [
            [
                [
                    _p(copy["visual"], styles["eyebrow"]),
                    *_bullet_list(
                        synthesis.visual_identity, styles["card_body"], limit=4, char_limit=140
                    ),
                ],
                [
                    _p(copy["signals"], styles["eyebrow"]),
                    *_bullet_list(
                        synthesis.audience_response_patterns,
                        styles["card_body"],
                        limit=4,
                        char_limit=140,
                    ),
                ],
            ]
        ],
        colWidths=[80 * mm, 80 * mm],
    )
    two_columns.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), WHITE),
                ("BACKGROUND", (1, 0), (1, 0), MINT),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 7 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7 * mm),
            ]
        )
    )
    story.extend([two_columns, PageBreak()])

    story.extend(
        _page_intro(copy, "actions", "actions_title", "actions_intro", styles, document.width)
    )
    action_table = Table(
        [
            [
                _action_card(copy["keep"], synthesis.keep, RED, styles),
                _action_card(copy["change"], synthesis.change, YELLOW, styles),
                _action_card(copy["test"], synthesis.tests, MINT, styles),
            ]
        ],
        colWidths=[53 * mm] * 3,
        hAlign="LEFT",
    )
    action_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    focus_text = (synthesis.change or synthesis.tests or synthesis.executive_summary)[0]
    story.extend(
        [
            action_table,
            Spacer(1, 8 * mm),
            _p(copy["focus"], styles["eyebrow"]),
            _dark_callout(focus_text, styles),
            PageBreak(),
        ]
    )

    story.extend(_page_intro(copy, "plan", "plan_title", "plan_intro", styles, document.width))
    plan_items = list(synthesis.thirty_day_plan[:4])
    fallback_plan = synthesis.tests or synthesis.change or [synthesis.account_positioning]
    while len(plan_items) < 4:
        plan_items.append(fallback_plan[len(plan_items) % len(fallback_plan)])
    for index, item in enumerate(plan_items, 1):
        story.extend(
            [
                _week_row(
                    index,
                    item,
                    [RED, YELLOW, MINT, BLUE][index - 1],
                    styles,
                    copy,
                ),
                Spacer(1, 4 * mm),
            ]
        )
    story.append(PageBreak())

    story.extend(
        _page_intro(copy, "measure", "measure_title", "measure_intro", styles, document.width)
    )
    measure_cards = [
        _metric_card(
            copy["reach"],
            _format_number(aggregates.get("median_reach"), copy["no_metric"]),
            copy["reach_note"],
            RED,
            styles,
        ),
        _metric_card(
            copy["saves"],
            _format_number(aggregates.get("total_saves"), copy["no_metric"]),
            copy["saves_note"],
            YELLOW,
            styles,
        ),
        _metric_card(
            copy["shares"],
            _format_number(aggregates.get("total_shares"), copy["no_metric"]),
            copy["shares_note"],
            MINT,
            styles,
        ),
        _metric_card(
            copy["rate"],
            _format_percent(aggregates.get("median_interaction_rate"), copy["no_metric"]),
            copy["rate_note"],
            BLUE,
            styles,
        ),
    ]
    story.extend(
        [
            Table([measure_cards], colWidths=[40 * mm] * 4, hAlign="LEFT"),
            Spacer(1, 10 * mm),
            _p(copy["routine"], styles["eyebrow"]),
        ]
    )
    routine = (
        "Review the last seven days at the same time each week. Compare posts by format, "
        "record the hook and topic, then choose one variable to change next."
        if language == "en"
        else (
            "Revisa los últimos siete días siempre a la misma hora. Compara por formato, "
            "registra hook y tema, y elige una sola variable para cambiar después."
        )
    )
    routine_box = Table([[_p(routine, styles["subtitle"])]], colWidths=[160 * mm])
    routine_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 6 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
            ]
        )
    )
    story.extend([routine_box, Spacer(1, 10 * mm), _p(copy["limitations"], styles["eyebrow"])])
    limitations = synthesis.limitations or [
        (
            "This audit reflects the posts and metrics available for this review. Use the "
            "recommendations as testable direction, then update them with new results."
        )
        if language == "en"
        else (
            "Esta auditoría refleja los posts y métricas disponibles para esta revisión. Usa "
            "las recomendaciones como dirección comprobable y actualízalas con nuevos "
            "resultados."
        )
    ]
    story.extend(_bullet_list(limitations, styles["body"], limit=3, char_limit=220))

    document.build(story)
    return output_path
