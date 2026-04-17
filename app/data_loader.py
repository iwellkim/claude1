"""업로드된 파일을 pandas DataFrame 으로 로딩."""
from __future__ import annotations

import io
from pathlib import Path
from typing import Tuple

import pandas as pd

SUPPORTED_EXTS = {".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json", ".parquet"}


def load_dataframe(path: str | Path) -> Tuple[pd.DataFrame, str]:
    """파일 확장자에 따라 적절한 파서를 사용해 DataFrame 을 만든다.

    한글 CSV 파일에서 자주 발생하는 cp949/utf-8-sig 인코딩 문제도 처리한다.
    반환값: (DataFrame, 사용된 로더 설명)
    """
    p = Path(path)
    ext = p.suffix.lower()

    if ext == ".csv":
        return _read_csv_smart(p), "CSV"
    if ext in {".tsv", ".txt"}:
        return _read_csv_smart(p, sep="\t"), "TSV"
    if ext in {".xlsx", ".xls"}:
        return pd.read_excel(p), "Excel"
    if ext == ".json":
        try:
            return pd.read_json(p), "JSON"
        except ValueError:
            return pd.read_json(p, lines=True), "JSON (lines)"
    if ext == ".parquet":
        return pd.read_parquet(p), "Parquet"

    raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}")


def _read_csv_smart(p: Path, sep: str | None = None) -> pd.DataFrame:
    raw = p.read_bytes()
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]
    last_err: Exception | None = None
    for enc in encodings:
        try:
            text = raw.decode(enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue
        try:
            if sep is None:
                return pd.read_csv(io.StringIO(text), sep=None, engine="python")
            return pd.read_csv(io.StringIO(text), sep=sep)
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise RuntimeError("CSV 파일을 읽을 수 없습니다")
