"""샘플 판매 데이터(CSV) 생성."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    rng = np.random.default_rng(42)
    n = 2000
    dates = pd.date_range("2024-01-01", "2024-12-31", freq="D")
    regions = ["서울", "부산", "대구", "인천", "광주", "대전"]
    channels = ["온라인", "오프라인", "모바일앱"]
    categories = ["가전", "식품", "의류", "도서", "뷰티"]
    df = pd.DataFrame(
        {
            "주문일자": rng.choice(dates, size=n),
            "지역": rng.choice(regions, size=n, p=[0.35, 0.2, 0.1, 0.15, 0.1, 0.1]),
            "채널": rng.choice(channels, size=n, p=[0.5, 0.3, 0.2]),
            "카테고리": rng.choice(categories, size=n),
            "수량": rng.integers(1, 12, size=n),
            "단가": rng.integers(5000, 200000, size=n),
            "할인율": rng.uniform(0, 0.3, size=n).round(2),
        }
    )
    df["매출"] = (df["수량"] * df["단가"] * (1 - df["할인율"])).round(0)
    # 일부 이상치 심기
    idx = rng.choice(n, 15, replace=False)
    df.loc[idx, "매출"] *= 8
    # 결측
    idx = rng.choice(n, 40, replace=False)
    df.loc[idx, "할인율"] = np.nan

    out = Path(__file__).resolve().parent.parent / "data" / "samples" / "sales_sample.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"샘플 저장: {out}  ({len(df):,} 행)")


if __name__ == "__main__":
    main()
