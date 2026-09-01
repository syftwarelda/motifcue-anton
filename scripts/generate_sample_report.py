from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

from anton.report import build_report
from anton.schemas import Account, AccountSynthesis, PostFinding, VisualAnalysis


def sample_thumbnail(path: Path, color: str, label: str) -> None:
    image = Image.new("RGB", (800, 800), color)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((70, 70, 730, 730), radius=48, outline="#F7F3EA", width=12)
    draw.text((110, 620), label, fill="#F7F3EA", stroke_width=1)
    image.save(path)


def main() -> None:
    output_dir = Path("tmp/pdfs")
    output_dir.mkdir(parents=True, exist_ok=True)
    colors = ["#D95C43", "#345A5E", "#7E6548"]
    findings = []
    for index, color in enumerate(colors, 1):
        thumbnail = output_dir / f"sample-{index}.jpg"
        sample_thumbnail(thumbnail, color, f"CREATOR POST {index}")
        findings.append(
            PostFinding(
                media_id=f"post-{index}",
                media_type="VIDEO" if index < 3 else "CAROUSEL_ALBUM",
                timestamp=datetime.now(UTC) - timedelta(days=index * 4),
                thumbnail_path=str(thumbnail),
                metrics={
                    "reach": 1800 - index * 220,
                    "views": 2400 - index * 250,
                    "total_interactions": 150 - index * 18,
                },
                rates={"interaction_rate_by_reach": 7.2},
                visual=VisualAnalysis(
                    summary=(
                        "A clear focal subject and a direct opening promise make "
                        "the idea easy to read."
                    ),
                    strengths=["Clear hierarchy", "Recognizable visual treatment"],
                    risks=["The supporting text could be shorter"],
                ),
            )
        )

    synthesis = AccountSynthesis(
        account_positioning=(
            "Practical ideas presented with a calm, recognizable visual point of view."
        ),
        executive_summary=[
            "Your strongest posts make the value obvious before asking for attention.",
            "A consistent visual treatment is beginning to make the account recognizable.",
            "Specific, useful promises create a stronger response than broad introductions.",
        ],
        audience_response_patterns=[
            "Posts with one clear takeaway lead the available reach and interaction results.",
            "Direct opening frames reduce the effort needed to understand the topic.",
            "Saveable, repeatable ideas create deeper value than context-only updates.",
        ],
        content_pillars=["Practical education", "Behind the process", "Point of view"],
        format_patterns=["Short video for discovery", "Carousels for reference"],
        visual_identity=[
            "Warm, grounded color choices",
            "A single focal subject",
            "Concise text placed with comfortable margins",
        ],
        keep=[
            "Lead with one useful promise.",
            "Keep the recognizable color treatment.",
            "Turn strong ideas into repeatable series.",
        ],
        change=[
            "Replace broad openings with a specific outcome.",
            "Give secondary text more breathing room.",
            "End educational posts with one next action.",
        ],
        tests=[
            "Test a question hook against a result-first hook.",
            "Publish one topic as both video and carousel.",
            "Repeat the best idea with a new example.",
        ],
        thirty_day_plan=[
            "Week 1: choose three repeatable themes and define one promise for each.",
            "Week 2: publish two controlled hook tests around the same topic.",
            "Week 3: turn the strongest idea into a short, recognizable series.",
            "Week 4: compare reach, saves, shares, and clarity; keep only the winning pattern.",
        ],
    )
    build_report(
        output_dir / "sample-creator-audit.pdf",
        "MotifCue",
        "en",
        Account(id="sample", username="yourhandle", followers_count=12400),
        synthesis,
        findings,
        {
            "analyzed_posts": 24,
            "median_reach": 1580,
            "median_interactions": 96,
        },
    )


if __name__ == "__main__":
    main()
