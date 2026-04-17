"""matplotlib 차트를 base64 PNG 로 반환하는 헬퍼.

한글 폰트는 app.fonts 에서 이미 설정되어 있다.
"""
from __future__ import annotations

import base64
import io

import matplotlib.pyplot as plt

from .fonts import KOREAN_FONT  # noqa: F401  (side effect: 한글 폰트 세팅)


def fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def new_fig(w: float = 8, h: float = 4.5):
    fig, ax = plt.subplots(figsize=(w, h))
    return fig, ax
