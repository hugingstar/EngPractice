#!/bin/bash

# 스크립트가 위치한 폴더로 이동 (이 스크립트를 어디서 실행하든 정상 작동하도록 보장)
cd "$(dirname "$0")"

echo "=========================================================="
echo "    Ggeolmu Language Pro 손상 오류(Gatekeeper) 해결기"
echo "=========================================================="
echo ""
echo "인터넷 다운로드로 인해 잠긴 앱의 보안 꼬리표를 제거합니다..."
echo ""

# 앱에 걸린 quarantine 속성 강제 제거
xattr -cr "Ggeolmu Language Pro.app"

echo "✅ 완료되었습니다!"
echo "이제 터미널 창을 끄고 'Ggeolmu Language Pro.app'을 더블클릭해서 실행하세요."
echo ""
read -n 1 -s -r -p "창을 닫으려면 아무 키나 누르세요..."
echo ""
