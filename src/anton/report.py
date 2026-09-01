from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from anton.schemas import Account, AccountSynthesis, PostFinding

INK = colors.HexColor("#161616")
CREAM = colors.HexColor("#F7F3EA")
RED = colors.HexColor("#F24735")
YELLOW = colors.HexColor("#F7D967")
WHITE = colors.white
MUTED = colors.HexColor("#625F59")
LINE = colors.HexColor("#D8D1C4")


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
        "report": "CREATOR AUDIT",
        "title": "Your content, made clearer.",
        "subtitle": "What is connecting, what to sharpen, and what to try next.",
        "snapshot": "Account snapshot",
        "followers": "Followers",
        "posts": "Posts reviewed",
        "reach": "Median reach",
        "interactions": "Median interactions",
        "read": "The read",
        "patterns": "What your audience responds to",
        "identity": "Your recognizable visual language",
        "top": "Posts worth learning from",
        "keep": "KEEP",
        "change": "SHARPEN",
        "test": "TEST NEXT",
        "plan": "Your next 30 days",
        "note": (
            "A useful direction, based on the content and performance available for this audit."
        ),
        "no_metric": "N/A",
    },
    "es": {
        "report": "AUDITORÍA PARA CREADORES",
        "title": "Tu contenido, con más claridad.",
        "subtitle": "Qué está conectando, qué pulir y qué probar ahora.",
        "snapshot": "Vista general",
        "followers": "Seguidores",
        "posts": "Piezas revisadas",
        "reach": "Alcance mediano",
        "interactions": "Interacciones medianas",
        "read": "La lectura principal",
        "patterns": "A qué responde tu audiencia",
        "identity": "Tu lenguaje visual reconocible",
        "top": "Publicaciones de las que aprender",
        "keep": "MANTÉN",
        "change": "PULIR",
        "test": "PRUEBA",
        "plan": "Tus próximos 30 días",
        "note": (
            "Una dirección útil basada en el contenido y rendimiento "
            "disponibles para esta auditoría."
        ),
        "no_metric": "N/D",
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


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle(
            "Eyebrow",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=8,
            leading=10,
            textColor=RED,
            spaceAfter=5,
            uppercase=True,
        ),
        "hero": ParagraphStyle(
            "Hero",
            parent=base["Title"],
            fontName="AntonSans-Bold",
            fontSize=34,
            leading=34,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontName="AntonSans",
            fontSize=13,
            leading=18,
            textColor=MUTED,
            spaceAfter=16,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="AntonSans-Bold",
            fontSize=22,
            leading=25,
            textColor=INK,
            spaceBefore=10,
            spaceAfter=10,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="AntonSans",
            fontSize=10.5,
            leading=15,
            textColor=INK,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "Small",
            parent=base["BodyText"],
            fontName="AntonSans",
            fontSize=8.5,
            leading=12,
            textColor=MUTED,
        ),
        "card_title": ParagraphStyle(
            "CardTitle",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=9,
            leading=11,
            textColor=INK,
            spaceAfter=5,
        ),
        "metric": ParagraphStyle(
            "Metric",
            parent=base["Normal"],
            fontName="AntonSans-Bold",
            fontSize=18,
            leading=20,
            textColor=INK,
            alignment=TA_CENTER,
        ),
        "metric_label": ParagraphStyle(
            "MetricLabel",
            parent=base["Normal"],
            fontName="AntonSans",
            fontSize=7.5,
            leading=9,
            textColor=MUTED,
            alignment=TA_CENTER,
        ),
    }


def _format_number(value: int | float | None, missing: str) -> str:
    if value is None:
        return missing
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def _bullet_list(items: Iterable[str], style: ParagraphStyle) -> list[Flowable]:
    output: list[Flowable] = []
    for item in items:
        output.append(Paragraph(f"• &nbsp;{item}", style))
    return output


def _metric_card(label: str, value: str, styles: dict) -> Table:
    card = Table(
        [[Paragraph(value, styles["metric"])], [Paragraph(label, styles["metric_label"])]],
        colWidths=[39 * mm],
        rowHeights=[11 * mm, 9 * mm],
    )
    card.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return card


def _action_card(title: str, items: list[str], background, styles: dict) -> Table:
    content: list[Flowable] = [Paragraph(title, styles["card_title"]), Spacer(1, 3)]
    content.extend(_bullet_list(items[:5], styles["body"]))
    table = Table([[content]], colWidths=[53 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), background),
                ("BOX", (0, 0), (-1, -1), 0, background),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 7 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7 * mm),
            ]
        )
    )
    return table


def _top_post_card(finding: PostFinding, rank: int, styles: dict) -> Table:
    image: Flowable
    if finding.thumbnail_path and Path(finding.thumbnail_path).exists():
        image = Image(finding.thumbnail_path, width=38 * mm, height=38 * mm, kind="proportional")
    else:
        image = Table(
            [[Paragraph(str(rank), styles["metric"])]], colWidths=[38 * mm], rowHeights=[38 * mm]
        )
        image.setStyle(
            TableStyle(
                [("BACKGROUND", (0, 0), (-1, -1), YELLOW), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
            )
        )

    metrics = finding.metrics
    copy = [
        Paragraph(
            f"#{rank} · {finding.media_type.replace('_', ' ').title()}", styles["card_title"]
        ),
        Paragraph(finding.visual.summary, styles["body"]),
        Paragraph(
            f"Reach: {_format_number(metrics.get('reach'), 'N/A')} &nbsp; "
            f"Interactions: {_format_number(metrics.get('total_interactions'), 'N/A')}",
            styles["small"],
        ),
    ]
    table = Table([[image, copy]], colWidths=[42 * mm, 119 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), WHITE),
                ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]
        )
    )
    return table


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
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"{brand_name} - @{account.username}",
        author=brand_name,
    )
    frame = Frame(
        document.leftMargin, document.bottomMargin, document.width, document.height, id="main"
    )

    def decorate(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(CREAM)
        canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
        canvas.setFillColor(INK)
        canvas.setFont("AntonSans-Bold", 7)
        canvas.drawString(22 * mm, 10 * mm, brand_name.upper())
        canvas.drawRightString(A4[0] - 22 * mm, 10 * mm, f"{doc.page:02d}")
        canvas.restoreState()

    document.addPageTemplates([PageTemplate(id="report", frames=[frame], onPage=decorate)])
    story: list[Flowable] = []

    story.extend(
        [
            Paragraph(copy["report"], styles["eyebrow"]),
            Paragraph(copy["title"], styles["hero"]),
            Paragraph(copy["subtitle"], styles["subtitle"]),
            Rule(document.width, RED, 3),
            Spacer(1, 10 * mm),
            Paragraph(f"@{account.username}", styles["section"]),
            Paragraph(synthesis.account_positioning, styles["subtitle"]),
            Spacer(1, 4 * mm),
            Paragraph(copy["snapshot"], styles["eyebrow"]),
        ]
    )
    cards = [
        _metric_card(
            copy["followers"], _format_number(account.followers_count, copy["no_metric"]), styles
        ),
        _metric_card(copy["posts"], str(aggregates["analyzed_posts"]), styles),
        _metric_card(
            copy["reach"], _format_number(aggregates["median_reach"], copy["no_metric"]), styles
        ),
        _metric_card(
            copy["interactions"],
            _format_number(aggregates["median_interactions"], copy["no_metric"]),
            styles,
        ),
    ]
    story.append(Table([cards], colWidths=[41 * mm] * 4, hAlign="LEFT"))
    story.extend([Spacer(1, 10 * mm), Paragraph(copy["read"], styles["section"])])
    story.extend(_bullet_list(synthesis.executive_summary, styles["body"]))

    story.extend([Spacer(1, 6 * mm), Paragraph(copy["patterns"], styles["section"])])
    story.extend(_bullet_list(synthesis.audience_response_patterns, styles["body"]))
    identity_section: list[Flowable] = [
        Spacer(1, 5 * mm),
        Paragraph(copy["identity"], styles["section"]),
        *_bullet_list(synthesis.visual_identity, styles["body"]),
    ]
    story.append(KeepTogether(identity_section))

    story.extend([Spacer(1, 7 * mm), Paragraph(copy["top"], styles["section"])])
    ranked = sorted(
        findings,
        key=lambda item: (
            item.metrics.get("total_interactions") or 0,
            item.metrics.get("reach") or 0,
        ),
        reverse=True,
    )[:5]
    for index, finding in enumerate(ranked, 1):
        story.extend([KeepTogether(_top_post_card(finding, index, styles)), Spacer(1, 4 * mm)])

    action_table = Table(
        [
            [
                _action_card(copy["keep"], synthesis.keep, WHITE, styles),
                _action_card(copy["change"], synthesis.change, YELLOW, styles),
                _action_card(copy["test"], synthesis.tests, RED, styles),
            ]
        ],
        colWidths=[55 * mm] * 3,
        hAlign="LEFT",
    )
    action_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(
        KeepTogether(
            [
                Spacer(1, 5 * mm),
                Paragraph(copy["plan"], styles["section"]),
                action_table,
            ]
        )
    )
    story.extend([Spacer(1, 9 * mm)])
    for index, item in enumerate(synthesis.thirty_day_plan, 1):
        row = Table(
            [[Paragraph(f"{index:02d}", styles["metric"]), Paragraph(item, styles["body"])]],
            colWidths=[18 * mm, 144 * mm],
        )
        row.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), INK),
                    ("TEXTCOLOR", (0, 0), (0, 0), WHITE),
                    ("BOX", (0, 0), (-1, -1), 0.8, LINE),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (1, 0), (1, 0), 6 * mm),
                    ("RIGHTPADDING", (1, 0), (1, 0), 6 * mm),
                    ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
                ]
            )
        )
        story.extend([KeepTogether(row), Spacer(1, 3 * mm)])
    story.extend(
        [
            Spacer(1, 7 * mm),
            Rule(document.width),
            Spacer(1, 3 * mm),
            Paragraph(copy["note"], styles["small"]),
        ]
    )

    document.build(story)
    return output_path
