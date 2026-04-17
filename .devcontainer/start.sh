#!/usr/bin/env bash
# Codespace 에 붙을 때마다 서버를 자동 실행.
# 이미 떠 있으면 그대로 둔다.

set -e

if pgrep -f "python run.py" >/dev/null 2>&1; then
    echo "==> 분석 플랫폼이 이미 실행 중입니다 (port 5000)."
    exit 0
fi

echo "==> Flask 분석 플랫폼 기동 → http://localhost:5000"
nohup python run.py > /tmp/app.log 2>&1 &
sleep 2
echo "==> 로그: tail -f /tmp/app.log"
echo "==> 우측 'PORTS' 탭 → 5000 포트 클릭하면 브라우저로 열립니다."
