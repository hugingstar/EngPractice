set appPath to POSIX path of (path to me)
set baseDir to do shell script "dirname " & quoted form of appPath

try
	display dialog "📖 Ggeolmu Language Pro" & return & return & "원하시는 작업을 선택하세요:" buttons {"▶ 실행 (Start)", "■ 종료 (Stop)", "취소"} default button "▶ 실행 (Start)" cancel button "취소" with title "Control Panel"
	set theButton to button returned of result
	
	if theButton is "▶ 실행 (Start)" then
		do shell script "pkill -f server.py || true; grep -q 'ggeolmu-language.com' /etc/hosts || echo '127.0.0.1 ggeolmu-language.com' >> /etc/hosts; cd " & quoted form of baseDir & "/LanguageLearner && /usr/bin/python3 server.py < /dev/null > server.log 2>&1 &" with administrator privileges
		
		display dialog "✅ 서버 실행 완료!" & return & return & "접속 주소: http://ggeolmu-language.com" & return & return & "아래 [접속하기] 버튼을 누르시면 웹 브라우저가 즉시 열립니다." buttons {"닫기", "접속하기"} default button "접속하기" with title "성공"
		set linkButton to button returned of result
		if linkButton is "접속하기" then
			do shell script "open 'http://ggeolmu-language.com'"
		end if
		
	else if theButton is "■ 종료 (Stop)" then
		do shell script "pkill -f server.py || true; sed -i '' '/ggeolmu-language.com/d' /etc/hosts" with administrator privileges
		display dialog "🛑 종료 완료" & return & return & "모든 세팅이 원상복구 되었습니다." buttons {"확인"} default button "확인" with title "종료"
	end if
on error number -128
	-- 사용자가 취소 버튼을 누른 경우 (에러 무시)
end try
