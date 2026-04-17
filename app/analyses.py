"""분석 실행기. 각 분석은 ``AnalysisBlock`` 목록을 반환한다."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats as sstats

from .charts import fig_to_base64, new_fig
from .profiler import ColumnProfile


@dataclass
class AnalysisBlock:
    kind: str  # 'text' | 'chart' | 'table' | 'kpi'
    title: str = ""
    text: str = ""
    chart_b64: str | None = None
    table_html: str | None = None
    kpis: list[dict[str, Any]] = field(default_factory=list)
    insights: list[str] = field(default_factory=list)


# ---------- utility ----------


def _numeric_cols(df: pd.DataFrame) -> list[str]:
    return df.select_dtypes(include=["number"]).columns.tolist()


def _coerce_datetime(df: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_datetime(df[col], errors="coerce")


def _fmt_num(v: float) -> str:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return "-"
    av = abs(v)
    if av >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f}B"
    if av >= 1_000_000:
        return f"{v/1_000_000:.2f}M"
    if av >= 1_000:
        return f"{v/1_000:.2f}K"
    if av >= 1:
        return f"{v:,.2f}"
    return f"{v:.4f}"


def _df_to_html(df: pd.DataFrame, max_rows: int = 20) -> str:
    d = df.head(max_rows)
    return d.to_html(classes="tbl", border=0, index=True, na_rep="-", justify="left")


# ---------- analyses ----------


def overview(df: pd.DataFrame, profiles: list[ColumnProfile]) -> list[AnalysisBlock]:
    n, m = df.shape
    miss = int(df.isna().sum().sum())
    dup = int(df.duplicated().sum())
    num_cols = _numeric_cols(df)

    kpis = [
        {"label": "행 수", "value": f"{n:,}"},
        {"label": "열 수", "value": f"{m:,}"},
        {"label": "결측치", "value": f"{miss:,}"},
        {"label": "중복 행", "value": f"{dup:,}"},
        {"label": "수치형 컬럼", "value": f"{len(num_cols)}"},
        {"label": "메모리(KB)", "value": f"{df.memory_usage(deep=True).sum()/1024:,.1f}"},
    ]
    blocks: list[AnalysisBlock] = [AnalysisBlock(kind="kpi", title="데이터 개요", kpis=kpis)]

    # 컬럼 요약 테이블
    rows = []
    for p in profiles:
        rows.append(
            {
                "컬럼": p.name,
                "역할": p.role,
                "dtype": p.dtype,
                "결측(%)": f"{p.missing_pct}%",
                "고유값": p.unique,
                "샘플": ", ".join(str(s) for s in p.sample[:3]),
            }
        )
    col_df = pd.DataFrame(rows)
    blocks.append(
        AnalysisBlock(
            kind="table",
            title="컬럼 프로파일",
            table_html=_df_to_html(col_df, max_rows=200),
        )
    )

    # 수치형 describe
    if num_cols:
        desc = df[num_cols].describe().T.round(3)
        blocks.append(
            AnalysisBlock(
                kind="table",
                title="수치형 변수 기술통계",
                table_html=_df_to_html(desc, max_rows=50),
            )
        )

    # 결측치 차트
    miss_s = df.isna().sum().sort_values(ascending=False)
    miss_s = miss_s[miss_s > 0]
    if not miss_s.empty:
        fig, ax = new_fig(8, max(3, 0.35 * len(miss_s) + 1))
        miss_s.iloc[::-1].plot(kind="barh", ax=ax, color="#ef4444")
        ax.set_title("컬럼별 결측치 개수")
        ax.set_xlabel("결측 수")
        blocks.append(AnalysisBlock(kind="chart", title="결측치 현황", chart_b64=fig_to_base64(fig)))

    insights = []
    if dup > 0:
        insights.append(f"중복 행이 {dup:,}건 존재합니다. 정제가 필요할 수 있습니다.")
    if miss > 0:
        insights.append(
            f"전체 결측치 {miss:,}개. 결측 비율이 높은 컬럼은 분석 전 대체/제거 전략을 결정하세요."
        )
    if not insights:
        insights.append("결측·중복 없는 깨끗한 데이터입니다.")
    blocks.append(AnalysisBlock(kind="text", title="요약 인사이트", insights=insights))
    return blocks


def distribution(df: pd.DataFrame, cols: list[str] | None = None) -> list[AnalysisBlock]:
    num_cols = cols or _numeric_cols(df)
    num_cols = [c for c in num_cols if c in df.columns][:8]
    blocks: list[AnalysisBlock] = []
    if not num_cols:
        return [AnalysisBlock(kind="text", title="분포 분석", text="수치형 컬럼이 없어 분석할 수 없습니다.")]

    # 히스토그램 그리드
    rows = (len(num_cols) + 2) // 3
    fig, axes = __import__("matplotlib.pyplot", fromlist=["subplots"]).subplots(
        rows, 3, figsize=(11, 3.2 * rows)
    )
    axes = np.atleast_2d(axes)
    for i, c in enumerate(num_cols):
        ax = axes[i // 3, i % 3]
        s = df[c].dropna()
        ax.hist(s, bins=30, color="#3b82f6", edgecolor="white")
        ax.set_title(f"{c} 분포")
        ax.set_xlabel(c)
        ax.set_ylabel("빈도")
    for j in range(len(num_cols), rows * 3):
        axes[j // 3, j % 3].axis("off")
    fig.tight_layout()
    blocks.append(AnalysisBlock(kind="chart", title="히스토그램", chart_b64=fig_to_base64(fig)))

    # 박스플롯
    fig, ax = new_fig(min(12, 1.6 * len(num_cols) + 3), 4.5)
    sns.boxplot(data=df[num_cols], ax=ax, palette="pastel")
    ax.set_title("박스플롯 (이상치 탐지용)")
    ax.tick_params(axis="x", rotation=20)
    blocks.append(AnalysisBlock(kind="chart", title="박스플롯", chart_b64=fig_to_base64(fig)))

    # 편향/첨도 요약
    stat_rows = []
    for c in num_cols:
        s = df[c].dropna()
        if s.empty:
            continue
        stat_rows.append(
            {
                "컬럼": c,
                "평균": round(float(s.mean()), 4),
                "중앙값": round(float(s.median()), 4),
                "표준편차": round(float(s.std()), 4),
                "왜도": round(float(s.skew()), 3),
                "첨도": round(float(s.kurt()), 3),
            }
        )
    if stat_rows:
        blocks.append(
            AnalysisBlock(
                kind="table",
                title="분포 요약",
                table_html=_df_to_html(pd.DataFrame(stat_rows), max_rows=50),
            )
        )

    insights = []
    for r in stat_rows:
        if abs(r["왜도"]) > 1:
            insights.append(f"'{r['컬럼']}' 은 왜도 {r['왜도']} 로 한쪽으로 치우쳐 있습니다.")
    if not insights:
        insights.append("분포는 대체로 대칭에 가깝습니다.")
    blocks.append(AnalysisBlock(kind="text", title="분포 인사이트", insights=insights[:6]))
    return blocks


def correlation(df: pd.DataFrame, cols: list[str] | None = None) -> list[AnalysisBlock]:
    num_cols = cols or _numeric_cols(df)
    num_cols = [c for c in num_cols if c in df.columns]
    if len(num_cols) < 2:
        return [AnalysisBlock(kind="text", title="상관관계", text="수치형 컬럼이 2개 이상 필요합니다.")]

    corr = df[num_cols].corr(numeric_only=True).round(3)
    fig, ax = new_fig(min(12, 0.8 * len(num_cols) + 4), min(10, 0.8 * len(num_cols) + 3))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="RdBu_r", center=0, ax=ax, cbar_kws={"shrink": 0.8})
    ax.set_title("상관계수 히트맵")
    blocks = [AnalysisBlock(kind="chart", title="상관 히트맵", chart_b64=fig_to_base64(fig))]

    # 강한 상관 탑
    pairs: list[tuple[str, str, float]] = []
    for i, a in enumerate(num_cols):
        for b in num_cols[i + 1 :]:
            pairs.append((a, b, float(corr.loc[a, b])))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    top = pairs[:8]
    if top:
        td = pd.DataFrame(top, columns=["변수 A", "변수 B", "상관계수"]).round(3)
        blocks.append(AnalysisBlock(kind="table", title="강한 상관 쌍", table_html=_df_to_html(td, max_rows=20)))

    insights = []
    for a, b, r in top[:5]:
        if abs(r) >= 0.7:
            direction = "강한 양의" if r > 0 else "강한 음의"
            insights.append(f"'{a}' 와 '{b}' 사이에 {direction} 상관 (r={r:.2f})이 있습니다.")
        elif abs(r) >= 0.4:
            direction = "중간 정도의 양의" if r > 0 else "중간 정도의 음의"
            insights.append(f"'{a}' 와 '{b}' 는 {direction} 상관 (r={r:.2f})을 보입니다.")
    if not insights:
        insights.append("뚜렷한 상관관계는 발견되지 않았습니다.")
    blocks.append(AnalysisBlock(kind="text", title="상관 인사이트", insights=insights))
    return blocks


def time_series(df: pd.DataFrame, date: str, value: str) -> list[AnalysisBlock]:
    if date not in df.columns or value not in df.columns:
        return [AnalysisBlock(kind="text", title="시계열", text="지정된 컬럼을 찾을 수 없습니다.")]
    t = _coerce_datetime(df, date)
    v = pd.to_numeric(df[value], errors="coerce")
    ts = pd.DataFrame({date: t, value: v}).dropna().sort_values(date)
    if ts.empty:
        return [AnalysisBlock(kind="text", title="시계열", text="유효한 데이터가 없습니다.")]

    # 일/주/월 중 관측치 수에 맞춰 리샘플
    span = (ts[date].max() - ts[date].min()).days or 1
    freq, label = ("D", "일별") if span <= 120 else (("W", "주별") if span <= 730 else ("M", "월별"))
    agg = ts.set_index(date)[value].resample(freq).sum()
    roll = agg.rolling(window=max(3, len(agg) // 12)).mean()

    fig, ax = new_fig(11, 4.5)
    ax.plot(agg.index, agg.values, label=f"{label} 합계", color="#2563eb")
    ax.plot(roll.index, roll.values, label="이동평균", color="#f97316", linewidth=2)
    ax.set_title(f"{value} 시계열 추세 ({label})")
    ax.set_xlabel(date)
    ax.set_ylabel(value)
    ax.legend()
    ax.grid(alpha=0.3)
    blocks = [AnalysisBlock(kind="chart", title="시계열 추세", chart_b64=fig_to_base64(fig))]

    # 기본 KPI
    total = float(agg.sum())
    peak = agg.idxmax()
    low = agg.idxmin()
    # 성장률: 앞쪽 20% vs 뒤쪽 20%
    if len(agg) >= 5:
        k = max(1, len(agg) // 5)
        early = agg.iloc[:k].mean()
        late = agg.iloc[-k:].mean()
        growth = (late / early - 1) * 100 if early else 0.0
    else:
        growth = 0.0

    kpis = [
        {"label": f"{value} 합계", "value": _fmt_num(total)},
        {"label": "최고 기간", "value": str(peak.date() if hasattr(peak, "date") else peak)},
        {"label": "최저 기간", "value": str(low.date() if hasattr(low, "date") else low)},
        {"label": "초반→후반 변화", "value": f"{growth:+.1f}%"},
    ]
    blocks.insert(0, AnalysisBlock(kind="kpi", title="시계열 KPI", kpis=kpis))

    insights = []
    if growth > 10:
        insights.append(f"'{value}' 가 초기 대비 후기에 {growth:.1f}% 증가하는 상승 추세입니다.")
    elif growth < -10:
        insights.append(f"'{value}' 가 초기 대비 후기에 {growth:.1f}% 감소하는 하락 추세입니다.")
    else:
        insights.append(f"'{value}' 는 기간 전체적으로 안정적인 흐름을 보입니다 ({growth:+.1f}%).")
    insights.append(f"최고 관측 기간은 {peak.date() if hasattr(peak,'date') else peak}, 최저는 {low.date() if hasattr(low,'date') else low} 입니다.")
    blocks.append(AnalysisBlock(kind="text", title="시계열 인사이트", insights=insights))
    return blocks


def segment(df: pd.DataFrame, group: str, value: str) -> list[AnalysisBlock]:
    if group not in df.columns or value not in df.columns:
        return [AnalysisBlock(kind="text", title="세그먼트", text="컬럼을 찾을 수 없습니다.")]
    v = pd.to_numeric(df[value], errors="coerce")
    d = pd.DataFrame({group: df[group], value: v}).dropna()
    if d.empty:
        return [AnalysisBlock(kind="text", title="세그먼트", text="유효한 데이터가 없습니다.")]

    agg = d.groupby(group)[value].agg(["sum", "mean", "count"]).sort_values("sum", ascending=False)
    agg.columns = ["합계", "평균", "건수"]
    top = agg.head(15)

    fig, ax = new_fig(10, max(3.5, 0.35 * len(top) + 1))
    top["합계"].iloc[::-1].plot(kind="barh", color="#10b981", ax=ax)
    ax.set_title(f"{group} 별 {value} 합계 TOP {len(top)}")
    ax.set_xlabel(value)
    blocks = [AnalysisBlock(kind="chart", title="세그먼트 합계", chart_b64=fig_to_base64(fig))]

    fig2, ax2 = new_fig(10, 4.5)
    sns.boxplot(data=d[d[group].isin(top.index[:10])], x=group, y=value, ax=ax2, palette="Set2")
    ax2.set_title(f"{group} 별 {value} 분포 (상위 10)")
    ax2.tick_params(axis="x", rotation=25)
    blocks.append(AnalysisBlock(kind="chart", title="세그먼트 분포", chart_b64=fig_to_base64(fig2)))

    blocks.append(
        AnalysisBlock(
            kind="table",
            title=f"{group} 별 요약",
            table_html=_df_to_html(agg.round(2), max_rows=30),
        )
    )

    total_sum = float(agg["합계"].sum())
    leader = agg.index[0]
    share = float(agg["합계"].iloc[0]) / total_sum * 100 if total_sum else 0
    insights = [
        f"최상위 세그먼트 '{leader}' 가 전체 '{value}' 의 {share:.1f}% 를 차지합니다.",
        f"세그먼트별 평균이 가장 높은 그룹은 '{agg['평균'].idxmax()}' 입니다.",
    ]
    if len(agg) >= 3:
        bottom = agg.index[-1]
        insights.append(f"하위 그룹 '{bottom}' 의 성과가 가장 낮아 개선 여지가 있습니다.")
    blocks.append(AnalysisBlock(kind="text", title="세그먼트 인사이트", insights=insights))
    return blocks


def crosstab(df: pd.DataFrame, row: str, col: str) -> list[AnalysisBlock]:
    if row not in df.columns or col not in df.columns:
        return [AnalysisBlock(kind="text", title="교차표", text="컬럼을 찾을 수 없습니다.")]
    ct = pd.crosstab(df[row], df[col])
    # 너무 크면 상위만
    if ct.shape[0] > 15:
        ct = ct.loc[ct.sum(axis=1).nlargest(15).index]
    if ct.shape[1] > 15:
        ct = ct[ct.sum(axis=0).nlargest(15).index]

    fig, ax = new_fig(min(12, 0.7 * ct.shape[1] + 3), min(10, 0.5 * ct.shape[0] + 2))
    sns.heatmap(ct, annot=True, fmt="d", cmap="Blues", ax=ax)
    ax.set_title(f"{row} × {col} 교차표")
    blocks = [AnalysisBlock(kind="chart", title="교차 히트맵", chart_b64=fig_to_base64(fig))]

    try:
        chi2, p, dof, _ = sstats.chi2_contingency(ct)
        insight = [f"카이제곱 검정 결과 χ²={chi2:.1f}, p={p:.4f} (자유도 {dof})."]
        if p < 0.05:
            insight.append("두 범주는 통계적으로 유의한 연관성을 보입니다.")
        else:
            insight.append("두 범주 사이에 뚜렷한 연관성은 관측되지 않습니다.")
    except Exception:
        insight = ["카이제곱 검정을 수행할 수 없습니다."]

    blocks.append(AnalysisBlock(kind="table", title="교차표", table_html=_df_to_html(ct, max_rows=30)))
    blocks.append(AnalysisBlock(kind="text", title="교차 인사이트", insights=insight))
    return blocks


def outliers(df: pd.DataFrame, cols: list[str] | None = None) -> list[AnalysisBlock]:
    num_cols = cols or _numeric_cols(df)
    num_cols = [c for c in num_cols if c in df.columns]
    if not num_cols:
        return [AnalysisBlock(kind="text", title="이상치", text="수치형 컬럼이 없습니다.")]

    rows = []
    for c in num_cols:
        s = df[c].dropna()
        if s.empty:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        out_iqr = int(((s < lo) | (s > hi)).sum())
        z = (s - s.mean()) / (s.std() if s.std() else 1)
        out_z = int((z.abs() > 3).sum())
        rows.append(
            {
                "컬럼": c,
                "IQR 하한": round(float(lo), 3),
                "IQR 상한": round(float(hi), 3),
                "IQR 이상치": out_iqr,
                "|z|>3 이상치": out_z,
                "비율(%)": round(out_iqr / len(s) * 100, 2),
            }
        )
    tdf = pd.DataFrame(rows).sort_values("IQR 이상치", ascending=False)
    blocks = [AnalysisBlock(kind="table", title="이상치 요약", table_html=_df_to_html(tdf, max_rows=30))]

    top = tdf.head(4)["컬럼"].tolist()
    if top:
        fig, axes = __import__("matplotlib.pyplot", fromlist=["subplots"]).subplots(
            1, len(top), figsize=(4 * len(top), 4)
        )
        if len(top) == 1:
            axes = [axes]
        for ax, c in zip(axes, top):
            sns.boxplot(y=df[c].dropna(), ax=ax, color="#f59e0b")
            ax.set_title(c)
        fig.tight_layout()
        blocks.append(AnalysisBlock(kind="chart", title="이상치 박스플롯", chart_b64=fig_to_base64(fig)))

    total_out = int(tdf["IQR 이상치"].sum())
    insights = [f"총 {total_out:,}건의 IQR 기반 이상치를 탐지했습니다."]
    worst = tdf.iloc[0] if not tdf.empty else None
    if worst is not None and worst["IQR 이상치"] > 0:
        insights.append(f"'{worst['컬럼']}' 의 이상치가 {int(worst['IQR 이상치']):,}건으로 가장 많습니다.")
    blocks.append(AnalysisBlock(kind="text", title="이상치 인사이트", insights=insights))
    return blocks


def top_bottom(df: pd.DataFrame, profiles: list[ColumnProfile]) -> list[AnalysisBlock]:
    # 매출성 수치 + 범주 자동 선택
    nums = [p.name for p in profiles if p.role == "numeric"]
    cats = [p.name for p in profiles if p.role == "categorical"]
    if not nums or not cats:
        return [AnalysisBlock(kind="text", title="TOP 분석", text="수치·범주 컬럼이 모두 필요합니다.")]

    from .profiler import _MONEY_WORDS

    target = next((n for n in nums if any(w in n.lower() for w in _MONEY_WORDS)), nums[0])
    group = cats[0]

    agg = df.groupby(group)[target].sum().sort_values(ascending=False)
    top = agg.head(10)
    bot = agg.tail(10).sort_values()

    fig, (ax1, ax2) = __import__("matplotlib.pyplot", fromlist=["subplots"]).subplots(
        1, 2, figsize=(12, 4.5)
    )
    top.iloc[::-1].plot(kind="barh", ax=ax1, color="#2563eb")
    ax1.set_title(f"TOP 10 {group} ({target})")
    bot.plot(kind="barh", ax=ax2, color="#ef4444")
    ax2.set_title(f"BOTTOM 10 {group} ({target})")
    fig.tight_layout()
    return [
        AnalysisBlock(kind="chart", title="TOP / BOTTOM", chart_b64=fig_to_base64(fig)),
        AnalysisBlock(
            kind="table",
            title=f"{group} 별 {target} 합계 TOP 20",
            table_html=_df_to_html(agg.head(20).to_frame("합계").round(2), max_rows=20),
        ),
    ]


def trend_by_segment(df: pd.DataFrame, date: str, group: str, value: str) -> list[AnalysisBlock]:
    if date not in df.columns or group not in df.columns or value not in df.columns:
        return [AnalysisBlock(kind="text", title="세그먼트 시계열", text="컬럼을 찾을 수 없습니다.")]
    t = _coerce_datetime(df, date)
    v = pd.to_numeric(df[value], errors="coerce")
    d = pd.DataFrame({"t": t, "g": df[group], "v": v}).dropna()
    if d.empty:
        return [AnalysisBlock(kind="text", title="세그먼트 시계열", text="유효 데이터가 없습니다.")]

    # 상위 그룹만
    top_groups = d.groupby("g")["v"].sum().nlargest(6).index.tolist()
    d = d[d["g"].isin(top_groups)]
    span = (d["t"].max() - d["t"].min()).days or 1
    freq = "D" if span <= 120 else ("W" if span <= 730 else "M")

    pivot = d.set_index("t").groupby("g")["v"].resample(freq).sum().unstack("g")
    fig, ax = new_fig(11, 5)
    pivot.plot(ax=ax)
    ax.set_title(f"{group} 별 {value} 시계열 추세")
    ax.set_xlabel(date)
    ax.set_ylabel(value)
    ax.grid(alpha=0.3)
    ax.legend(title=group, bbox_to_anchor=(1.02, 1), loc="upper left")
    return [AnalysisBlock(kind="chart", title="세그먼트별 추세", chart_b64=fig_to_base64(fig))]


def kmeans_cluster(df: pd.DataFrame, cols: list[str] | None = None, k: int = 4) -> list[AnalysisBlock]:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    num_cols = cols or _numeric_cols(df)
    num_cols = [c for c in num_cols if c in df.columns][:6]
    if len(num_cols) < 2:
        return [AnalysisBlock(kind="text", title="군집", text="수치형 컬럼이 2개 이상 필요합니다.")]

    X = df[num_cols].dropna()
    if len(X) < k * 3:
        return [AnalysisBlock(kind="text", title="군집", text="군집 수행에 필요한 데이터가 부족합니다.")]

    Xs = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=k, n_init="auto", random_state=42).fit(Xs)
    labels = pd.Series(km.labels_, index=X.index, name="cluster")
    summary = X.assign(cluster=labels).groupby("cluster").agg(["mean", "count"])
    # 컬럼 다중 계층을 예쁘게 편 테이블
    means = X.assign(cluster=labels).groupby("cluster").mean().round(3)
    means["건수"] = labels.value_counts().sort_index()

    # 첫 두 축에 산점도
    fig, ax = new_fig(8, 5)
    scatter = ax.scatter(X[num_cols[0]], X[num_cols[1]], c=labels, cmap="tab10", alpha=0.7)
    ax.set_xlabel(num_cols[0])
    ax.set_ylabel(num_cols[1])
    ax.set_title(f"K-평균 군집 (k={k})")
    legend = ax.legend(*scatter.legend_elements(), title="군집", loc="best")
    ax.add_artist(legend)
    blocks = [AnalysisBlock(kind="chart", title="군집 산점도", chart_b64=fig_to_base64(fig))]
    blocks.append(AnalysisBlock(kind="table", title="군집별 평균", table_html=_df_to_html(means, max_rows=10)))

    insights = [f"데이터를 {k} 개 군집으로 나누었습니다."]
    largest = means["건수"].idxmax()
    insights.append(f"가장 큰 군집은 {largest} 번이며 {int(means.loc[largest,'건수']):,}건 입니다.")
    blocks.append(AnalysisBlock(kind="text", title="군집 인사이트", insights=insights))
    return blocks


# ---------- dispatcher ----------


DEFAULT_DISPATCH: dict[str, Any] = {
    "overview": overview,
    "distribution": distribution,
    "correlation": correlation,
    "time_series": time_series,
    "segment": segment,
    "crosstab": crosstab,
    "outliers": outliers,
    "top_bottom": top_bottom,
    "trend_by_segment": trend_by_segment,
    "kmeans": kmeans_cluster,
}


def run_analysis(
    key: str,
    df: pd.DataFrame,
    profiles: list[ColumnProfile],
    params: dict[str, Any] | None = None,
) -> list[AnalysisBlock]:
    params = params or {}
    func = DEFAULT_DISPATCH.get(key)
    if func is None:
        return [AnalysisBlock(kind="text", title="알 수 없는 분석", text=f"'{key}' 는 지원하지 않는 분석입니다.")]

    if key == "overview":
        return overview(df, profiles)
    if key == "top_bottom":
        return top_bottom(df, profiles)
    if key == "distribution":
        return distribution(df, params.get("columns"))
    if key == "correlation":
        return correlation(df, params.get("columns"))
    if key == "outliers":
        return outliers(df, params.get("columns"))
    if key == "time_series":
        return time_series(df, params["date"], params["value"])
    if key == "segment":
        return segment(df, params["group"], params["value"])
    if key == "crosstab":
        return crosstab(df, params["row"], params["col"])
    if key == "trend_by_segment":
        return trend_by_segment(df, params["date"], params["group"], params["value"])
    if key == "kmeans":
        return kmeans_cluster(df, params.get("columns"), int(params.get("k", 4)))

    return func(df, profiles)
