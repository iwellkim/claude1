"""한글 폰트 안전 로더.

matplotlib 에서 한글이 깨지지 않도록 시스템에 설치된 한글 폰트를
탐지해 전역으로 설정한다. 없는 경우 프로젝트 ``assets/fonts`` 아래 번들된
NanumGothic 폰트 파일을 등록한다.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import matplotlib
from matplotlib import font_manager, rcParams

_CANDIDATES = [
    # macOS
    "AppleGothic",
    "Apple SD Gothic Neo",
    # Windows
    "Malgun Gothic",
    "맑은 고딕",
    # Linux 에 자주 설치되는 한글 폰트
    "NanumGothic",
    "Nanum Gothic",
    "NanumBarunGothic",
    "Noto Sans CJK KR",
    "Noto Sans KR",
    "UnDotum",
    "Baekmuk Gulim",
    # CJK 통합 폰트(한글 글리프 포함) — 최후 폴백
    "WenQuanYi Zen Hei",
    "Source Han Sans KR",
    "Source Han Sans K",
]

_BUNDLED_FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _find_installed_korean_font() -> Optional[str]:
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in _CANDIDATES:
        if name in installed:
            return name
    return None


def _register_bundled_fonts() -> Optional[str]:
    """assets/fonts 에 있는 .ttf/.otf 파일을 matplotlib 에 등록한다."""
    if not _BUNDLED_FONT_DIR.exists():
        return None
    registered: list[str] = []
    for path in _BUNDLED_FONT_DIR.glob("*.[to]t[fc]"):
        try:
            font_manager.fontManager.addfont(str(path))
            registered.append(font_manager.FontProperties(fname=str(path)).get_name())
        except Exception:
            continue
    for name in registered:
        if name in {f.name for f in font_manager.fontManager.ttflist}:
            return name
    return registered[0] if registered else None


def setup_korean_font() -> str:
    """한글이 깨지지 않도록 matplotlib 기본 폰트를 설정하고 사용된 폰트 이름을 반환."""
    matplotlib.use("Agg", force=True)

    font_name = _find_installed_korean_font()
    if font_name is None:
        font_name = _register_bundled_fonts()

    if font_name:
        rcParams["font.family"] = font_name
    else:
        # 마지막 폴백 - 적어도 네모(□)는 피하도록 sans-serif 유지
        rcParams["font.family"] = "DejaVu Sans"
        font_name = "DejaVu Sans"

    # 마이너스 기호가 깨지지 않도록
    rcParams["axes.unicode_minus"] = False
    # 보고서용 기본 스타일
    rcParams["figure.dpi"] = 110
    rcParams["savefig.dpi"] = 140
    rcParams["figure.autolayout"] = True
    rcParams["axes.titlesize"] = 13
    rcParams["axes.labelsize"] = 11

    os.environ.setdefault("MPLBACKEND", "Agg")
    return font_name


KOREAN_FONT = setup_korean_font()
