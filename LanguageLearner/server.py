import http.server
import socketserver
import json
import urllib.parse
from youtube_transcript_api import YouTubeTranscriptApi
import re
import traceback
import warnings

# Suppress urllib3 SSL warnings on macOS
warnings.filterwarnings("ignore", module="urllib3")

PORT = 8000

class TranscriptRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/api/transcript':
            # Extract query parameters
            query_params = urllib.parse.parse_qs(parsed_path.query)
            video_id = query_params.get('videoId', [None])[0]
            script_lang = query_params.get('scriptLang', ['en'])[0]
            dict_lang = query_params.get('dictLang', ['ko'])[0]
            
            if not video_id:
                self.send_error(400, "Missing videoId parameter")
                return
                
            try:
                import os
                import requests
                import http.cookiejar
                
                # Setup session with optional cookies to bypass YouTube IP blocks
                session = requests.Session()
                
                # server.py가 위치한 폴더의 cookies.txt 절대 경로 계산
                base_dir = os.path.dirname(os.path.abspath(__file__))
                cookie_path = os.path.join(base_dir, "cookies.txt")
                cookie_error_msg = ""
                
                if os.path.exists(cookie_path):
                    try:
                        cookie_jar = http.cookiejar.MozillaCookieJar(cookie_path)
                        cookie_jar.load(ignore_discard=True, ignore_expires=True)
                        session.cookies = cookie_jar
                    except Exception as e:
                        cookie_error_msg = str(e)
                        print("Cookie load error:", e)

                # Try fetching transcripts
                try:
                    transcript_list = YouTubeTranscriptApi(http_client=session).list(video_id)
                except Exception as e:
                    if "blocked" in str(e).lower() or "too many requests" in str(e).lower():
                        # 쿠키 파일 감지 및 파싱 상태 진단
                        if not os.path.exists(cookie_path):
                            cookie_status = "❌ 쿠키 파일('cookies.txt')을 서버가 찾을 수 없습니다. 경로 마운트 또는 생성 상태를 확인해 주세요."
                        elif cookie_error_msg:
                            cookie_status = f"❌ 쿠키 파일 로드 실패: {cookie_error_msg} (복사 중 탭 구분자가 깨졌거나 파일이 손상되었습니다.)"
                        else:
                            cookie_status = "✅ 쿠키 파일이 정상 로드되었으나 유튜브 측에서 차단했습니다. (쿠키의 유효기간 만료 또는 비활성 쿠키)"

                        raise Exception(
                            f"유튜브 접속 차단(Rate Limit)이 감지되었습니다.\n\n"
                            f"[💡 현재 서버의 쿠키 상태]\n{cookie_status}\n\n"
                            "👉 [해결 방법]\n"
                            "1. 로컬 실행 중: 앱 폴더(LanguageLearner) 안에 'cookies.txt' 파일을 넣어주세요.\n"
                            "2. 클라우드(Render) 배포 중:\n"
                            "   - 저장소가 비공개(Private)인 경우: 프로젝트 폴더에 'cookies.txt'를 넣은 뒤 GitHub에 푸시하세요.\n"
                            "   - 저장소가 공개(Public)인 경우: 보안 유출 방지를 위해 Render.com 서비스 관리자 화면의 [Environment] -> [Secret Files] 메뉴에서 Filename을 'cookies.txt'로 지정하고 쿠키 값을 붙여넣어 생성해 주세요."
                        )
                    else:
                        raise e

                def fetch_lang_data(lang):
                    """Fetch transcript in a given language, with auto-translate fallback."""
                    # 1. Try direct match
                    try:
                        t = transcript_list.find_transcript([lang])
                        return t.fetch()
                    except:
                        pass
                    # 2. Try generated transcript
                    try:
                        t = transcript_list.find_generated_transcript([lang])
                        return t.fetch()
                    except:
                        pass
                    # 3. Fallback: translate any translatable transcript
                    for t in transcript_list:
                        if t.is_translatable:
                            try:
                                return t.translate(lang).fetch()
                            except:
                                pass
                    return None

                # Fetch script (main) and dict (translation/A/) data
                warnings = []
                lang_names = {'ko': '한국어', 'en': '영어', 'ja': '일본어', 'zh': '중국어'}

                script_data = fetch_lang_data(script_lang)
                if not script_data:
                    # Fallback: use the auto-detected original transcript
                    for t in transcript_list:
                        try:
                            script_data = t.fetch()
                            break
                        except:
                            pass
                    if script_data:
                        script_lang_name = lang_names.get(script_lang, script_lang)
                        warnings.append(f"'{script_lang_name}' 자막이 없어 원본 언어로 표시합니다.")
                    else:
                        raise Exception("이 영상에서 사용 가능한 자막을 찾을 수 없습니다.")

                dict_data = fetch_lang_data(dict_lang)
                if not dict_data:
                    dict_lang_name = lang_names.get(dict_lang, dict_lang)
                    warnings.append(f"'{dict_lang_name}' 해석을 가져올 수 없어 A/ 줄이 비어 있습니다.")

                # Build the response array
                mock_transcript = []
                
                def find_closest_dict(start_time):
                    if not dict_data: return ""
                    closest = None
                    min_diff = 9999
                    for item in dict_data:
                        diff = abs(item.start - start_time)
                        if diff < min_diff:
                            min_diff = diff
                            closest = item
                    return closest.text if closest and min_diff < 5 else ""

                grouped_data = []
                current_sentence = []
                current_start = 0
                current_duration = 0
                
                import re

                for item in script_data[:300]: # Use script_data (user-selected main language)
                    text = item.text.replace('\n', ' ').strip()
                    if not current_sentence:
                        current_start = item.start
                        current_duration = item.duration
                    else:
                        gap = item.start - (current_start + current_duration)
                        if gap > 1.5:
                            grouped_data.append({
                                "words": current_sentence,  # list of (text, start) tuples
                                "start": current_start,
                                "duration": current_duration
                            })
                            current_sentence = []
                            current_start = item.start
                            current_duration = item.duration
                        else:
                            current_duration = (item.start + item.duration) - current_start
                            
                    current_sentence.append((text, item.start))  # store (text, start_time)
                    
                    if re.search(r'[.?!]$', text):
                        grouped_data.append({
                            "words": current_sentence,
                            "start": current_start,
                            "duration": current_duration
                        })
                        current_sentence = []
                        current_start = 0
                        current_duration = 0

                if current_sentence:
                    grouped_data.append({
                        "words": current_sentence,
                        "start": current_start,
                        "duration": current_duration
                    })

                speaker_emojis = ['🐶', '🐱', '🦊', '🐻', '🐼', '🐨', '🐰', '🐯']
                current_speaker_idx = 0

                for item in grouped_data:
                    start = item['start']
                    duration = item['duration']
                    
                    # Rebuild text from (text, start) word tuples
                    word_tuples = item['words']
                    text = " ".join(t for t, _ in word_tuples)
                    
                    target_text = find_closest_dict(start).replace('\n', ' ')
                    
                    # Replace ">>" with a rotating emoji
                    if '>>' in text:
                        text = text.replace('>>', speaker_emojis[current_speaker_idx % len(speaker_emojis)])
                        current_speaker_idx += 1
                    
                    # Build word objects with per-word startTime
                    word_objs = []
                    for chunk_text, chunk_start in word_tuples:
                        chunk_words = chunk_text.split()
                        for i, w in enumerate(chunk_words):
                            word_objs.append({
                                "text": w,
                                "mean": "",
                                "pron": "",
                                "startTime": chunk_start  # each word gets its source item's start time
                            })

                    mock_transcript.append({
                        "startTime": start,
                        "endTime": start + duration,
                        "text": text,
                        "translation": target_text,
                        "words": word_objs
                    })
                
                # Send response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response_body = {
                    "warnings": warnings,
                    "transcript": mock_transcript
                }
                self.wfile.write(json.dumps(response_body, ensure_ascii=False).encode('utf-8'))
                
            except Exception as e:
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                error_resp = {"error": str(e)}
                self.wfile.write(json.dumps(error_resp).encode('utf-8'))
        else:
            # Serve standard static files
            super().do_GET()

# To allow address reuse
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("", PORT), TranscriptRequestHandler) as httpd:
    print(f"Serving API and static files at port {PORT}")
    httpd.serve_forever()
