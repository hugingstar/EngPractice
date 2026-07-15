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

import requests

class TranscriptItem:
    def __init__(self, text, start, duration):
        self.text = text
        self.start = start
        self.duration = duration

def fetch_transcript_without_cookies(video_id, lang='en'):
    """유튜브 TimedText API를 직접 파싱하여 쿠키 없이 자막을 획득합니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9,ko;q=0.8'
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        res = requests.get(url, headers=headers, timeout=10)
        html = res.text
        
        # ytInitialPlayerResponse 찾기
        match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html)
        if not match:
            match = re.search(r'var ytInitialPlayerResponse\s*=\s*({.+?});', html)
        if not match:
            return None
            
        player_response = json.loads(match.group(1))
        caption_tracks = player_response.get('captions', {}).get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
        
        # 원하는 언어 코드 매칭
        track_url = None
        for track in caption_tracks:
            if track.get('languageCode') == lang:
                track_url = track.get('baseUrl')
                break
        
        # 원하는 언어가 없고 다른 언어만 존재할 시 첫 번째 트랙을 폴백으로 지정
        if not track_url and caption_tracks:
            track_url = caption_tracks[0].get('baseUrl')
            
        if not track_url:
            return None

        # fmt=json을 덧붙여 다이렉트 자막 요청 (CORS나 쿠키 차단이 없음)
        caption_res = requests.get(track_url + "&fmt=json", headers=headers, timeout=10)
        caption_json = caption_res.json()
        
        events = caption_json.get('events', [])
        parsed_list = []
        for event in events:
            if 'segs' in event:
                text = "".join(seg.get('utf8', '') for seg in event['segs']).strip()
                if text:
                    start = event.get('tStartMs', 0) / 1000.0
                    duration = event.get('dDurationMs', 0) / 1000.0
                    parsed_list.append(TranscriptItem(text, start, duration))
        return parsed_list
    except Exception as e:
        print("Fallback scraper failed:", e)
        return None

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
                    # 1. Try with official YouTubeTranscriptApi (using cookies if available)
                    transcript_list = YouTubeTranscriptApi(http_client=session).list(video_id)
                    
                    def fetch_lang_data(lang):
                        """Fetch transcript in a given language, with auto-translate fallback."""
                        try:
                            t = transcript_list.find_transcript([lang])
                            return t.fetch()
                        except: pass
                        try:
                            t = transcript_list.find_generated_transcript([lang])
                            return t.fetch()
                        except: pass
                        for t in transcript_list:
                            if t.is_translatable:
                                try: return t.translate(lang).fetch()
                                except: pass
                        return None

                    # Fetch script (main) and dict (translation/A/) data
                    warnings = []
                    lang_names = {'ko': '한국어', 'en': '영어', 'ja': '일본어', 'zh': '중국어'}

                    script_data = fetch_lang_data(script_lang)
                    if not script_data:
                        for t in transcript_list:
                            try:
                                script_data = t.fetch()
                                break
                            except: pass
                        if script_data:
                            script_lang_name = lang_names.get(script_lang, script_lang)
                            warnings.append(f"'{script_lang_name}' 자막이 없어 원본 언어로 표시합니다.")
                        else:
                            raise Exception("이 영상에서 사용 가능한 자막을 찾을 수 없습니다.")

                    dict_data = fetch_lang_data(dict_lang)
                    if not dict_data:
                        dict_lang_name = lang_names.get(dict_lang, dict_lang)
                        warnings.append(f"'{dict_lang_name}' 해석을 가져올 수 없어 A/ 줄이 비어 있습니다.")

                except Exception as e:
                    # 2. Fallback: Try with cookieless scraper if official API fails (Rate Limit, etc.)
                    print("유튜브 공식 API 호출 실패. 쿠키리스 우회 스크래퍼로 시도합니다:", e)
                    warnings = []
                    lang_names = {'ko': '한국어', 'en': '영어', 'ja': '일본어', 'zh': '중국어'}
                    
                    script_data = fetch_transcript_without_cookies(video_id, script_lang)
                    if not script_data:
                        # Try fallback language (English)
                        script_data = fetch_transcript_without_cookies(video_id, 'en')
                        if script_data:
                            warnings.append(f"'{lang_names.get(script_lang, script_lang)}' 자막이 없어 영어 자막으로 대체합니다.")
                    
                    if not script_data:
                        raise Exception(
                            f"유튜브 접속 차단(Rate Limit) 우회 시도 및 자막 추출에 모두 실패했습니다.\n\n"
                            f"[💡 현재 서버의 쿠키 상태]\n"
                            f"{'❌ 쿠키 파일 없음' if not os.path.exists(cookie_path) else '❌ 쿠키 로드 실패: ' + cookie_error_msg if cookie_error_msg else '✅ 쿠키 파일 로드됨 (유튜브 측 거부)'}\n\n"
                            f"영상 자체에 실제 사용 가능한 자막이 있는지 확인해 주세요."
                        )
                    
                    dict_data = fetch_transcript_without_cookies(video_id, dict_lang)
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
