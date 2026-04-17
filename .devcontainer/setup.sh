#!/usr/bin/env bash
# Codespaces 최초 생성 시 1회 실행.
# 한글 폰트 + 파이썬 의존성 설치.

set -e

echo "==> 한글 폰트 설치 (matplotlib 차트 깨짐 방지)"
sudo apt-get update -y
sudo apt-get install -y --no-install-recommends \
    fonts-nanum \
    fonts-nanum-coding \
    fonts-noto-cjk \
    fontconfig
sudo fc-cache -fv

echo "==> 파이썬 패키지 설치"
pip install --upgrade pip
pip install -r requirements.txt

echo "==> 샘플 데이터 생성"
python scripts/make_sample_data.py || true

# matplotlib 폰트 캐시 비우기 — 새 폰트를 읽어들이게 함
rm -rf ~/.cache/matplotlib 2>/dev/null || true

echo "==> 셋업 완료."
