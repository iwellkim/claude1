"""Flask 서버 - 업로드, 프로파일링, 분석, 보고서 생성 엔드포인트."""
from __future__ import annotations

import os
import pickle
import uuid
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

# 한글 폰트 세팅을 차트보다 먼저 수행
from .fonts import KOREAN_FONT  # noqa: F401

from .analyses import AnalysisBlock, run_analysis
from .custom_request import parse_request
from .data_loader import SUPPORTED_EXTS, load_dataframe
from .profiler import (
    profile_dataframe,
    profiles_to_dicts,
    recommend_analyses,
    recs_to_dicts,
)
from .report import build_executive_summary, render_report, section_from_blocks


BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "data" / "uploads"
SESSION_DIR = BASE_DIR / "data" / "sessions"
REPORT_DIR = BASE_DIR / "data" / "reports"
for d in (UPLOAD_DIR, SESSION_DIR, REPORT_DIR):
    d.mkdir(parents=True, exist_ok=True)


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200MB

    @app.get("/")
    def index():
        return render_template("index.html", font_name=KOREAN_FONT)

    @app.post("/api/upload")
    def api_upload():
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify(error="파일이 업로드되지 않았습니다."), 400
        fname = secure_filename(f.filename)
        ext = Path(fname).suffix.lower()
        if ext not in SUPPORTED_EXTS:
            return jsonify(error=f"지원하지 않는 확장자: {ext}"), 400

        session_id = uuid.uuid4().hex[:12]
        path = UPLOAD_DIR / f"{session_id}_{fname}"
        f.save(path)

        try:
            df, loader = load_dataframe(path)
        except Exception as e:  # pragma: no cover
            return jsonify(error=f"파일을 읽는 중 오류: {e}"), 400

        profiles, summary = profile_dataframe(df)
        recs = recommend_analyses(df, profiles)

        # 세션 저장 (파일 경로 + 원본 이름 + 추천 목록)
        session_blob = {
            "filename": fname,
            "path": str(path),
            "loader": loader,
            "recommendations": [r.__dict__ for r in recs],
        }
        (SESSION_DIR / f"{session_id}.pkl").write_bytes(pickle.dumps(session_blob))

        return jsonify(
            session_id=session_id,
            filename=fname,
            loader=loader,
            summary=summary,
            profiles=profiles_to_dicts(profiles),
            recommendations=recs_to_dicts(recs),
        )

    @app.post("/api/analyze")
    def api_analyze():
        payload: dict[str, Any] = request.get_json(force=True) or {}
        session_id = payload.get("session_id")
        selected: list[int] = payload.get("selected") or []
        custom: str = (payload.get("custom") or "").strip()

        sess_path = SESSION_DIR / f"{session_id}.pkl"
        if not session_id or not sess_path.exists():
            return jsonify(error="세션이 존재하지 않습니다. 파일을 다시 업로드하세요."), 400
        sess = pickle.loads(sess_path.read_bytes())

        try:
            df, _ = load_dataframe(sess["path"])
        except Exception as e:
            return jsonify(error=f"파일을 다시 읽는 중 오류: {e}"), 400
        profiles, summary = profile_dataframe(df)

        sections: list[dict[str, Any]] = []
        recs = sess["recommendations"]

        # 개요는 항상 포함
        ov_blocks = run_analysis("overview", df, profiles)
        sections.append(section_from_blocks("데이터 개요 & 기술통계", ov_blocks))

        # 사용자가 선택한 추천 분석
        for idx in selected:
            if not isinstance(idx, int) or idx < 0 or idx >= len(recs):
                continue
            rec = recs[idx]
            if rec["key"] == "overview":
                continue  # 이미 포함
            params = dict(rec.get("params") or {})
            if rec.get("columns"):
                params.setdefault("columns", rec["columns"])
            blocks = run_analysis(rec["key"], df, profiles, params)
            sections.append(section_from_blocks(rec["title"], blocks))

        # 사용자 커스텀 요청
        if custom:
            for chunk in [c.strip() for c in custom.split(";") if c.strip()]:
                key, params, desc = parse_request(chunk, df, profiles)
                blocks = run_analysis(key, df, profiles, params)
                sections.append(section_from_blocks(f"사용자 요청 · {desc}", blocks))

        summary_bullets = build_executive_summary(sections)
        html = render_report(
            filename=sess["filename"],
            summary=summary,
            sections=sections,
            executive_summary=summary_bullets,
            font_name=KOREAN_FONT,
        )
        report_name = f"{session_id}_report.html"
        (REPORT_DIR / report_name).write_text(html, encoding="utf-8")
        return jsonify(report_url=f"/reports/{report_name}", sections=len(sections))

    @app.get("/reports/<path:name>")
    def get_report(name: str):
        return send_from_directory(REPORT_DIR, name)

    @app.get("/healthz")
    def health():
        return jsonify(status="ok", font=KOREAN_FONT)

    return app


app = create_app()


if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=bool(os.environ.get("DEBUG")))
