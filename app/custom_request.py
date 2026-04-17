"""자연어 분석 요청을 분석 키와 파라미터로 변환."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from .profiler import ColumnProfile


_KOR_NUM = {
    "매출": ["매출", "수익", "판매", "revenue", "sales"],
    "수량": ["수량", "건수", "주문수", "qty", "quantity"],
    "가격": ["가격", "단가", "price"],
}


def _find_column(text: str, df: pd.DataFrame, role_prefer: str | None = None, profiles: list[ColumnProfile] | None = None) -> str | None:
    cols = list(df.columns)
    # 완전 일치 먼저
    for c in cols:
        if c and str(c) in text:
            return c
    low_text = text.lower()
    for c in cols:
        if str(c).lower() in low_text:
            return c
    # 역할 기반 폴백
    if profiles and role_prefer:
        for p in profiles:
            if p.role == role_prefer:
                return p.name
    return None


def parse_request(
    text: str,
    df: pd.DataFrame,
    profiles: list[ColumnProfile],
) -> tuple[str, dict[str, Any], str]:
    """자연어 요청을 (분석 키, 파라미터, 설명) 으로 변환.

    분석 키를 찾지 못하면 ('overview', {}, 설명) 을 돌려준다.
    """
    t = text.strip()
    lower = t.lower()

    # 1) 시계열 관련
    if re.search(r"(시계열|추세|trend|월별|일별|주별|시간별|기간별)", t, re.IGNORECASE):
        date_col = _find_column(t, df, role_prefer="datetime", profiles=profiles)
        if not date_col:
            date_col = next((p.name for p in profiles if p.role in ("datetime", "datetime-str")), None)
        value_col = _find_column(t, df, role_prefer="numeric", profiles=profiles) or _pick_money_like(profiles)
        group_col = _find_group_col(t, profiles)
        if date_col and value_col and group_col and re.search(r"(세그먼트|그룹|별|분류)", t):
            return "trend_by_segment", {"date": date_col, "group": group_col, "value": value_col}, f"{group_col} 별 {value_col} 시계열 추세"
        if date_col and value_col:
            return "time_series", {"date": date_col, "value": value_col}, f"{date_col} 기준 {value_col} 시계열 추세"

    # 2) 상관
    if re.search(r"(상관|correlation|관계|연관)", t, re.IGNORECASE):
        return "correlation", {}, "수치 변수 간 상관관계"

    # 3) 이상치
    if re.search(r"(이상치|outlier|이상값|특이값)", t, re.IGNORECASE):
        return "outliers", {}, "이상치 탐지"

    # 4) 분포
    if re.search(r"(분포|distribution|히스토그램|histogram|박스플롯|boxplot)", t, re.IGNORECASE):
        return "distribution", {}, "수치형 변수 분포"

    # 5) 세그먼트 / 그룹
    if re.search(r"(세그먼트|segment|그룹|별 비교|비교|랭킹|순위|top|bottom|상위|하위)", t, re.IGNORECASE):
        group = _find_group_col(t, profiles)
        value = _find_column(t, df, role_prefer="numeric", profiles=profiles) or _pick_money_like(profiles)
        if group and value:
            return "segment", {"group": group, "value": value}, f"{group} 별 {value} 비교"
        return "top_bottom", {}, "TOP / BOTTOM 분석"

    # 6) 교차표
    if re.search(r"(교차|crosstab|cross|분할표|연관)", t, re.IGNORECASE):
        cats = [p.name for p in profiles if p.role == "categorical"]
        if len(cats) >= 2:
            return "crosstab", {"row": cats[0], "col": cats[1]}, f"{cats[0]} × {cats[1]}"

    # 7) 군집
    if re.search(r"(군집|클러스터|cluster|kmeans)", t, re.IGNORECASE):
        return "kmeans", {"k": _parse_k(t) or 4}, "K-평균 군집화"

    # 8) 요약/개요
    if re.search(r"(요약|개요|overview|summary|describe|기술통계)", t, re.IGNORECASE):
        return "overview", {}, "전반적 개요"

    return "overview", {}, f"요청 '{text}' 를 정확히 해석하지 못해 전반적 개요를 제공합니다."


def _pick_money_like(profiles: list[ColumnProfile]) -> str | None:
    for p in profiles:
        low = p.name.lower()
        for words in _KOR_NUM.values():
            if any(w in low or w in p.name for w in words):
                if p.role == "numeric":
                    return p.name
    # fallback first numeric
    for p in profiles:
        if p.role == "numeric":
            return p.name
    return None


def _find_group_col(text: str, profiles: list[ColumnProfile]) -> str | None:
    for p in profiles:
        if p.role == "categorical" and (p.name in text or p.name.lower() in text.lower()):
            return p.name
    for p in profiles:
        if p.role == "categorical":
            return p.name
    return None


def _parse_k(text: str) -> int | None:
    m = re.search(r"(?:k\s*=\s*|군집\s*수\s*|cluster\s*)(\d+)", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(?:개|그룹|군집)", text)
    if m:
        return int(m.group(1))
    return None
