"""DataFrame 프로파일링 및 분석 추천 엔진."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
)


# 열 의미 추정을 돕는 키워드
_MONEY_WORDS = ("매출", "금액", "가격", "비용", "수익", "revenue", "sales", "price", "cost", "amount", "profit")
_COUNT_WORDS = ("수량", "건수", "count", "qty", "quantity", "orders", "visits")
_DATE_WORDS = ("날짜", "일자", "일시", "date", "time", "datetime", "ymd", "기간")
_ID_WORDS = ("id", "번호", "코드", "code", "no.", "key")
_CAT_WORDS = ("지역", "카테고리", "분류", "부서", "국가", "등급", "상품", "제품", "채널", "region", "category", "type", "segment", "dept", "country", "grade", "product", "channel")


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    role: str  # numeric / datetime / categorical / text / boolean / id
    missing: int
    missing_pct: float
    unique: int
    sample: list[Any] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    key: str
    title: str
    description: str
    columns: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


def _guess_role(name: str, series: pd.Series) -> str:
    low = str(name).lower()
    if is_datetime64_any_dtype(series):
        return "datetime"
    if is_bool_dtype(series):
        return "boolean"
    if is_numeric_dtype(series):
        if any(w in low for w in _ID_WORDS) and series.is_unique:
            return "id"
        return "numeric"

    # 문자열 계열
    sample = series.dropna().astype(str)
    if not sample.empty:
        try:
            parsed = pd.to_datetime(sample.head(30), errors="coerce", utc=False)
            if parsed.notna().mean() > 0.8 and any(w in low for w in _DATE_WORDS) or parsed.notna().mean() > 0.9:
                return "datetime-str"
        except Exception:
            pass
    unique_ratio = series.nunique(dropna=True) / max(len(series), 1)
    if unique_ratio < 0.3 or series.nunique(dropna=True) <= 30:
        return "categorical"
    if any(w in low for w in _ID_WORDS):
        return "id"
    return "text"


def _coerce_datetime(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_datetime(df[col], errors="coerce")


def profile_dataframe(df: pd.DataFrame) -> tuple[list[ColumnProfile], dict[str, Any]]:
    """각 컬럼의 프로파일과 전체 요약을 반환."""
    profiles: list[ColumnProfile] = []
    n = len(df)
    for col in df.columns:
        s = df[col]
        role = _guess_role(col, s)
        missing = int(s.isna().sum())
        unique = int(s.nunique(dropna=True))
        stats: dict[str, Any] = {}

        if role == "numeric":
            desc = s.describe(percentiles=[0.25, 0.5, 0.75])
            stats = {k: _safe_number(v) for k, v in desc.items()}
        elif role in ("datetime", "datetime-str"):
            parsed = _coerce_datetime(df, col) if role == "datetime-str" else s
            if parsed.notna().any():
                stats = {
                    "min": str(parsed.min()),
                    "max": str(parsed.max()),
                    "span_days": int((parsed.max() - parsed.min()).days) if pd.notna(parsed.min()) else 0,
                }
        elif role == "categorical":
            vc = s.value_counts(dropna=True).head(5)
            stats = {"top": {str(k): int(v) for k, v in vc.items()}}
        elif role == "boolean":
            vc = s.value_counts(dropna=True)
            stats = {"top": {str(k): int(v) for k, v in vc.items()}}

        sample = s.dropna().head(5).tolist()
        sample = [_to_native(x) for x in sample]

        profiles.append(
            ColumnProfile(
                name=str(col),
                dtype=str(s.dtype),
                role=role,
                missing=missing,
                missing_pct=round(missing / n * 100, 2) if n else 0.0,
                unique=unique,
                sample=sample,
                stats=stats,
            )
        )

    summary = {
        "rows": int(n),
        "cols": int(df.shape[1]),
        "missing_total": int(df.isna().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "memory_kb": round(df.memory_usage(deep=True).sum() / 1024, 1),
    }
    return profiles, summary


def recommend_analyses(df: pd.DataFrame, profiles: list[ColumnProfile]) -> list[Recommendation]:
    numerics = [p.name for p in profiles if p.role == "numeric"]
    cats = [p.name for p in profiles if p.role == "categorical"]
    dates = [p.name for p in profiles if p.role in ("datetime", "datetime-str")]

    recs: list[Recommendation] = []

    recs.append(
        Recommendation(
            key="overview",
            title="전반적 개요 및 기술 통계",
            description="데이터의 행/열 구성, 결측·중복, 주요 수치형 컬럼의 분포와 요약통계를 한눈에 확인합니다.",
        )
    )

    if len(numerics) >= 1:
        recs.append(
            Recommendation(
                key="distribution",
                title="수치형 변수 분포 분석",
                description="히스토그램·박스플롯으로 각 수치 변수의 분포, 이상치, 편향을 시각화합니다.",
                columns=numerics[:6],
            )
        )

    if len(numerics) >= 2:
        recs.append(
            Recommendation(
                key="correlation",
                title="상관관계·변수 간 관계",
                description="수치형 변수들 사이의 피어슨 상관을 히트맵으로 보여주고 의미 있는 관계를 해석합니다.",
                columns=numerics,
            )
        )

    if dates and numerics:
        # 매출성 지표 우선 선택
        target = _pick_money_like(numerics) or numerics[0]
        recs.append(
            Recommendation(
                key="time_series",
                title="시계열 추세 분석",
                description=f"'{dates[0]}' 기준으로 '{target}' 의 시간별 추세·계절성·이동평균을 분석합니다.",
                columns=[dates[0], target],
                params={"date": dates[0], "value": target},
            )
        )

    if cats and numerics:
        cat = _pick_name(cats, _CAT_WORDS) or cats[0]
        target = _pick_money_like(numerics) or numerics[0]
        recs.append(
            Recommendation(
                key="segment",
                title="세그먼트별 비교",
                description=f"'{cat}' 별 '{target}' 의 합계·평균·분포를 비교해 성과 차이를 파악합니다.",
                columns=[cat, target],
                params={"group": cat, "value": target},
            )
        )

    if len(cats) >= 2:
        recs.append(
            Recommendation(
                key="crosstab",
                title="범주 교차 분석",
                description=f"'{cats[0]}' 와 '{cats[1]}' 의 교차표·히트맵으로 조합별 빈도 구조를 살핍니다.",
                columns=cats[:2],
                params={"row": cats[0], "col": cats[1]},
            )
        )

    if len(numerics) >= 2:
        recs.append(
            Recommendation(
                key="outliers",
                title="이상치 탐지",
                description="IQR·Z-score 기반으로 수치 변수의 이상치를 식별하고 요약합니다.",
                columns=numerics,
            )
        )

    if _has_money_and_customer(df, profiles):
        recs.append(
            Recommendation(
                key="top_bottom",
                title="상·하위 TOP 리스트",
                description="매출·수량 기준 상위/하위 항목을 추려 비즈니스 인사이트를 도출합니다.",
            )
        )

    if dates and cats and numerics:
        target = _pick_money_like(numerics) or numerics[0]
        recs.append(
            Recommendation(
                key="trend_by_segment",
                title="세그먼트별 시계열 추세",
                description=f"'{cats[0]}' 그룹별 '{target}' 시간 추세를 비교합니다.",
                params={"date": dates[0], "group": cats[0], "value": target},
            )
        )

    if len(numerics) >= 3:
        recs.append(
            Recommendation(
                key="kmeans",
                title="K-평균 군집화",
                description="수치형 변수들을 기반으로 자동으로 군집을 찾고 각 군집의 특성을 비교합니다.",
                columns=numerics[:6],
            )
        )

    return recs


# ---------- helpers ----------


def _pick_money_like(cols: list[str]) -> str | None:
    for c in cols:
        low = c.lower()
        if any(w in low for w in _MONEY_WORDS):
            return c
    for c in cols:
        low = c.lower()
        if any(w in low for w in _COUNT_WORDS):
            return c
    return None


def _pick_name(cols: list[str], words: tuple[str, ...]) -> str | None:
    for c in cols:
        if any(w in c.lower() for w in words):
            return c
    return None


def _has_money_and_customer(df: pd.DataFrame, profiles: list[ColumnProfile]) -> bool:
    has_money = any(any(w in p.name.lower() for w in _MONEY_WORDS) for p in profiles)
    has_cat = any(p.role == "categorical" for p in profiles)
    return has_money and has_cat


def _safe_number(v: Any) -> Any:
    try:
        if isinstance(v, (int, np.integer)):
            return int(v)
        if isinstance(v, (float, np.floating)):
            if np.isnan(v) or np.isinf(v):
                return None
            return round(float(v), 4)
    except Exception:
        pass
    return str(v)


def _to_native(v: Any) -> Any:
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        x = float(v)
        return None if (np.isnan(x) or np.isinf(x)) else x
    if isinstance(v, (pd.Timestamp,)):
        return str(v)
    return v


def profiles_to_dicts(profiles: list[ColumnProfile]) -> list[dict[str, Any]]:
    return [asdict(p) for p in profiles]


def recs_to_dicts(recs: list[Recommendation]) -> list[dict[str, Any]]:
    return [asdict(r) for r in recs]
