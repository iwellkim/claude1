"""분석 결과를 HTML 보고서로 렌더링."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .analyses import AnalysisBlock

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_report(
    filename: str,
    summary: dict[str, Any],
    sections: list[dict[str, Any]],
    executive_summary: list[str],
    font_name: str,
) -> str:
    tmpl = _env.get_template("report.html")
    return tmpl.render(
        filename=filename,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        summary=summary,
        sections=sections,
        executive_summary=executive_summary,
        font_name=font_name,
    )


def section_from_blocks(title: str, blocks: list[AnalysisBlock]) -> dict[str, Any]:
    return {
        "title": title,
        "blocks": [asdict(b) for b in blocks],
    }


def build_executive_summary(sections: list[dict[str, Any]]) -> list[str]:
    """각 섹션의 'text' 블록 인사이트를 모아 핵심 요약 생성."""
    bullets: list[str] = []
    for sec in sections:
        for b in sec["blocks"]:
            if b.get("kind") == "text":
                for ins in b.get("insights", []):
                    bullets.append(f"[{sec['title']}] {ins}")
    seen = set()
    unique: list[str] = []
    for b in bullets:
        if b not in seen:
            seen.add(b)
            unique.append(b)
    return unique[:10]
