import http.server
import socketserver
import json
import urllib.parse
import os
from youtube_transcript_api import YouTubeTranscriptApi
import re
import traceback
import warnings
import xml.etree.ElementTree as ET
import html
import base64

# Suppress urllib3 SSL warnings on macOS
warnings.filterwarnings("ignore", module="urllib3")

import requests
import http.cookiejar

# 전역 Session 생성 (쿠키 지원)
global_session = requests.Session()
cookie_paths = [
    '/etc/secrets/cookies.txt',          # 1. Render.com Secret File 경로
    'cookies.txt',                       # 2. 로컬 실행 (LanguageLearner 폴더)
    'LanguageLearner/cookies.txt'        # 3. 로컬 실행 (루트 폴더)
]
cookie_path = next((p for p in cookie_paths if os.path.exists(p)), None)

if cookie_path:
    try:
        cj = http.cookiejar.MozillaCookieJar(cookie_path)
        cj.load(ignore_discard=True, ignore_expires=True)
        global_session.cookies.update(cj)
        print(f"Loaded cookies from {cookie_path}")
    except Exception as e:
        print(f"Failed to load cookies: {e}")

class TranscriptItem:
    def __init__(self, text, start, duration):
        self.text = text
        self.start = start
        self.duration = duration

def fetch_transcript_via_innertube(video_id, lang='en'):
    """YouTube InnerTube API를 사용해 자막을 가져옵니다."""
    try:
        url = "https://www.youtube.com/youtubei/v1/get_transcript"
        
        def build_params(video_id, lang):
            def encode_string(field_number, value):
                tag = (field_number << 3) | 2
                encoded = value.encode('utf-8')
                return bytes([tag]) + encode_varint(len(encoded)) + encoded
            def encode_varint(n):
                result = []
                while n > 0x7F:
                    result.append((n & 0x7F) | 0x80)
                    n >>= 7
                result.append(n)
                return bytes(result)
            inner = encode_string(1, video_id)
            lang_proto = encode_string(1, lang)
            outer_tag = (3 << 3) | 2
            inner2 = bytes([outer_tag]) + encode_varint(len(lang_proto)) + lang_proto
            proto = inner + inner2
            return base64.b64encode(proto).decode('utf-8')
        
        params = build_params(video_id, lang)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Content-Type': 'application/json',
            'X-YouTube-Client-Name': '1',
            'X-YouTube-Client-Version': '2.20240101.00.00',
        }
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20240101.00.00",
                    "hl": lang,
                    "gl": "US"
                }
            },
            "params": params
        }
        
        res = global_session.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code != 200:
            return None
        
        data = res.json()
        actions = data.get('actions', [])
        parsed_list = []
        for action in actions:
            renderer = action.get('updateEngagementPanelAction', {}) \
                            .get('content', {}) \
                            .get('transcriptRenderer', {}) \
                            .get('content', {}) \
                            .get('transcriptSearchPanelRenderer', {}) \
                            .get('body', {}) \
                            .get('transcriptSegmentListRenderer', {}) \
                            .get('initialSegments', [])
            for seg in renderer:
                segment = seg.get('transcriptSegmentRenderer', {})
                start_ms = int(segment.get('startMs', 0))
                end_ms = int(segment.get('endMs', 0))
                text_runs = segment.get('snippet', {}).get('runs', [])
                text = ''.join(r.get('text', '') for r in text_runs).strip()
                if text:
                    start = start_ms / 1000.0
                    duration = (end_ms - start_ms) / 1000.0
                    parsed_list.append(TranscriptItem(text, start, duration))
        
        if parsed_list:
            print(f"InnerTube API 성공 (lang={lang})")
        return parsed_list if parsed_list else None
    except Exception as e:
        print("InnerTube API failed:", e)
        return None


def fetch_transcript_without_cookies(video_id, lang='en'):
    """유튜브 HTML을 직접 파싱하여 자막 URL을 추출합니다."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        res = global_session.get(url, headers=headers, timeout=10)
        page_html = res.text

        # ytInitialPlayerResponse 추출 (개선된 방식)
        player_response = None
        patterns = [
            r'ytInitialPlayerResponse\s*=\s*({.+?})\s*;',
            r'var ytInitialPlayerResponse\s*=\s*({.+?})\s*;',
            r'"playerResponse"\s*:\s*"({.+?})"',
        ]
        for pattern in patterns:
            match = re.search(pattern, page_html, re.DOTALL)
            if match:
                try:
                    raw = match.group(1)
                    player_response = json.loads(raw)
                    break
                except json.JSONDecodeError:
                    continue
        
        # 패턴이 안 되면 split 방식으로 추출
        if not player_response:
            try:
                idx = page_html.index('ytInitialPlayerResponse')
                sub = page_html[idx:]
                brace_start = sub.index('{')
                depth = 0
                for i, ch in enumerate(sub[brace_start:], brace_start):
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                    if depth == 0:
                        raw = sub[brace_start:i + 1]
                        player_response = json.loads(raw)
                        break
            except Exception:
                return None

        if not player_response:
            return None

        caption_tracks = (
            player_response
            .get('captions', {})
            .get('playerCaptionsTracklistRenderer', {})
            .get('captionTracks', [])
        )

        track_url = None
        # 원하는 언어 먼저 시도
        for track in caption_tracks:
            if track.get('languageCode', '').startswith(lang):
                track_url = track.get('baseUrl')
                break
        # 없으면 첫 번째 트랙
        if not track_url and caption_tracks:
            track_url = caption_tracks[0].get('baseUrl')

        if not track_url:
            return None

        # JSON 형식으로 자막 요청
        caption_res = global_session.get(track_url + "&fmt=json3", headers=headers, timeout=10)
        if caption_res.status_code != 200:
            # XML 형식으로 fallback
            xml_res = global_session.get(track_url, headers=headers, timeout=10)
            if xml_res.status_code != 200:
                return None
            root = ET.fromstring(xml_res.text)
            parsed_list = []
            for text_tag in root.findall('text'):
                raw_text = text_tag.text
                if raw_text:
                    text = html.unescape(raw_text).replace('\n', ' ').strip()
                    start = float(text_tag.get('start', 0))
                    duration = float(text_tag.get('dur', 0))
                    parsed_list.append(TranscriptItem(text, start, duration))
            if parsed_list:
                print("YouTube HTML scraper (XML) 성공")
            return parsed_list if parsed_list else None

        caption_json = caption_res.json()
        events = caption_json.get('events', [])
        parsed_list = []
        for event in events:
            if 'segs' in event:
                text = "".join(seg.get('utf8', '') for seg in event['segs']).strip()
                if text and text != '\n':
                    start = event.get('tStartMs', 0) / 1000.0
                    duration = event.get('dDurationMs', 0) / 1000.0
                    parsed_list.append(TranscriptItem(text, start, duration))
        
        if parsed_list:
            print("YouTube HTML scraper (JSON) 성공")
        return parsed_list if parsed_list else None
    except Exception as e:
        print("HTML scraper failed:", e)
        return None


def fetch_transcript_from_invidious(video_id, lang='en'):
    """Invidious 프록시 API를 통해 자막을 가져옵니다."""
    # 2025년 기준 동작 중인 인스턴스
    instances = [
        "https://invidious.nerdvpn.de",
        "https://inv.nadeko.net",
        "https://invidious.privacyredirect.com",
        "https://yewtu.be",
        "https://invidious.flokinet.to",
    ]

    lang_map = {
        'ko': ['Korean', 'ko', '한국어'],
        'en': ['English', 'en', '영어'],
        'ja': ['Japanese', 'ja', '일본어'],
        'zh': ['Chinese', 'zh', '중국어'],
    }
    target_keys = lang_map.get(lang, [lang])

    for instance in instances:
        try:
            url = f"{instance}/api/v1/videos/{video_id}"
            res = global_session.get(url, timeout=6)
            if res.status_code != 200:
                continue
            data = res.json()
            captions = data.get("captions", [])

            target_track = None
            for track in captions:
                code = track.get("languageCode", "").lower()
                label = track.get("label", "").lower()
                if any(k.lower() in code or k.lower() in label for k in target_keys):
                    target_track = track
                    break

            if not target_track and captions:
                target_track = captions[0]

            if target_track:
                caption_url = target_track.get("url", "")
                if not caption_url.startswith("http"):
                    caption_url = f"{instance}{caption_url}"

                cap_res = global_session.get(caption_url + "&format=json3", timeout=6)
                if cap_res.status_code == 200:
                    try:
                        cap_json = cap_res.json()
                        events = cap_json.get("events", [])
                        parsed_list = []
                        for event in events:
                            if 'segs' in event:
                                text = "".join(seg.get('utf8', '') for seg in event['segs']).strip()
                                if text and text != '\n':
                                    start = event.get('tStartMs', 0) / 1000.0
                                    duration = event.get('dDurationMs', 0) / 1000.0
                                    parsed_list.append(TranscriptItem(text, start, duration))
                        if parsed_list:
                            print(f"Invidious 우회 성공 (Instance: {instance})")
                            return parsed_list
                    except Exception:
                        pass
        except Exception as e:
            print(f"Invidious {instance} failed:", e)
            continue
    return None


def build_transcript_response(script_data, dict_data, warnings):
    """script_data와 dict_data로부터 최종 transcript JSON 배열을 빌드합니다."""
    mock_transcript = []

    def find_closest_dict(start_time):
        if not dict_data:
            return ""
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

    for item in script_data[:300]:
        text = item.text.replace('\n', ' ').strip()
        if not current_sentence:
            current_start = item.start
            current_duration = item.duration
        else:
            gap = item.start - (current_start + current_duration)
            if gap > 1.5:
                grouped_data.append({
                    "words": current_sentence,
                    "start": current_start,
                    "duration": current_duration
                })
                current_sentence = []
                current_start = item.start
                current_duration = item.duration
            else:
                current_duration = (item.start + item.duration) - current_start

        current_sentence.append((text, item.start))

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

        word_tuples = item['words']
        text = " ".join(t for t, _ in word_tuples)

        target_text = find_closest_dict(start).replace('\n', ' ')

        if '>>' in text:
            text = text.replace('>>', speaker_emojis[current_speaker_idx % len(speaker_emojis)])
            current_speaker_idx += 1

        word_objs = []
        for chunk_text, chunk_start in word_tuples:
            chunk_words = chunk_text.split()
            for w in chunk_words:
                word_objs.append({
                    "text": w,
                    "mean": "",
                    "pron": "",
                    "startTime": chunk_start
                })

        mock_transcript.append({
            "startTime": start,
            "endTime": start + duration,
            "text": text,
            "translation": target_text,
            "words": word_objs
        })

    return mock_transcript

PORT = int(os.environ.get('PORT', 8000))


class TranscriptRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)

        if parsed_path.path == '/api/transcript':
            query_params = urllib.parse.parse_qs(parsed_path.query)
            video_id = query_params.get('videoId', [None])[0]
            script_lang = query_params.get('scriptLang', ['en'])[0]
            dict_lang = query_params.get('dictLang', ['ko'])[0]

            if not video_id:
                self.send_error(400, "Missing videoId parameter")
                return

            try:
                warn_list = []
                lang_names = {'ko': '한국어', 'en': '영어', 'ja': '일본어', 'zh': '중국어'}
                script_data = None
                dict_data = None

                # ── 0차: 로컬 캐시 확인 (확장 프로그램 등에서 사전에 추출해 전송한 경우) ──
                cache_dir = os.path.join(os.path.dirname(__file__), '.cache', 'transcripts')

                def load_from_cache(lang):
                    if not os.path.exists(cache_dir):
                        return None
                    
                    # 1. 정확히 일치하는 자막 파일 확인 (예: en.json)
                    cache_file = os.path.join(cache_dir, f"{video_id}_{lang}.json")
                    if os.path.exists(cache_file):
                        try:
                            with open(cache_file, 'r', encoding='utf-8') as f:
                                caption_json = json.load(f)
                            return parse_caption_json(caption_json)
                        except Exception as e:
                            print(f"로컬 캐시 파싱 실패 ({cache_file}): {e}")

                    # 2. 부분 일치하는 자막 파일 확인 (예: en-US -> en.json 혹은 그 반대)
                    for fname in os.listdir(cache_dir):
                        if fname.startswith(f"{video_id}_") and fname.endswith(".json"):
                            file_lang = fname[len(video_id)+1 : -5]
                            if file_lang.startswith(lang) or lang.startswith(file_lang):
                                cache_file = os.path.join(cache_dir, fname)
                                try:
                                    with open(cache_file, 'r', encoding='utf-8') as f:
                                        caption_json = json.load(f)
                                    return parse_caption_json(caption_json)
                                except Exception as e:
                                    print(f"로컬 캐시 파싱 실패 ({cache_file}): {e}")
                    return None

                def parse_caption_json(caption_json):
                    events = caption_json.get('events', [])
                    parsed_list = []
                    for event in events:
                        if 'segs' in event:
                            text = "".join(seg.get('utf8', '') for seg in event['segs']).strip()
                            if text and text != '\n':
                                start = event.get('tStartMs', 0) / 1000.0
                                duration = event.get('dDurationMs', 0) / 1000.0
                                parsed_list.append(TranscriptItem(text, start, duration))
                    return parsed_list if parsed_list else None

                script_data = load_from_cache(script_lang)
                if script_data:
                    print(f"0차 로컬 캐시 (스크립트={script_lang}) 로드 성공")

                dict_data = load_from_cache(dict_lang)
                if dict_data:
                    print(f"0차 로컬 캐시 (해석={dict_lang}) 로드 성공")

                # ── 1차: YouTubeTranscriptApi (가장 안정적) ──
                if not script_data:
                    try:
                        # 쿠키가 탑재된 global_session을 주입
                        api = YouTubeTranscriptApi(http_client=global_session)
                        transcript_list = api.list(video_id)

                        def fetch_lang_via_api(lang):
                            try:
                                return transcript_list.find_transcript([lang]).fetch()
                            except Exception:
                                pass
                            try:
                                return transcript_list.find_generated_transcript([lang]).fetch()
                            except Exception:
                                pass
                            for t in transcript_list:
                                if t.is_translatable:
                                    try:
                                        return t.translate(lang).fetch()
                                    except Exception:
                                        pass
                            return None

                        script_raw = fetch_lang_via_api(script_lang)
                        if script_raw:
                            # FetchedTranscript → TranscriptItem 변환
                            script_data = [TranscriptItem(s.text, s.start, s.duration) for s in script_raw]

                        dict_raw = fetch_lang_via_api(dict_lang)
                        if dict_raw:
                            dict_data = [TranscriptItem(s.text, s.start, s.duration) for s in dict_raw]

                        if not script_data:
                            # 첫 번째 트랙 fallback
                            for t in transcript_list:
                                try:
                                    raw = t.fetch()
                                    script_data = [TranscriptItem(s.text, s.start, s.duration) for s in raw]
                                    warn_list.append(f"'{lang_names.get(script_lang, script_lang)}' 자막이 없어 원본 언어로 표시합니다.")
                                    break
                                except Exception:
                                    pass

                        if script_data:
                            print("1차 YouTubeTranscriptApi 성공")

                    except Exception as e:
                        print(f"1차 YouTubeTranscriptApi 실패: {e}")

                # ── 2차: YouTube HTML 직접 파싱 ──
                if not script_data:
                    print("2차 YouTube HTML scraper 시도...")
                    script_data = fetch_transcript_without_cookies(video_id, script_lang)
                    if not script_data and script_lang != 'en':
                        script_data = fetch_transcript_without_cookies(video_id, 'en')
                        if script_data:
                            warn_list.append(f"'{lang_names.get(script_lang, script_lang)}' 자막 없음 — 영어로 대체합니다.")

                # ── 3차: InnerTube API ──
                if not script_data:
                    print("3차 InnerTube API 시도...")
                    script_data = fetch_transcript_via_innertube(video_id, script_lang)
                    if not script_data and script_lang != 'en':
                        script_data = fetch_transcript_via_innertube(video_id, 'en')
                        if script_data:
                            warn_list.append(f"'{lang_names.get(script_lang, script_lang)}' 자막 없음 — 영어로 대체합니다.")

                # ── 4차: Invidious 프록시 ──
                if not script_data:
                    print("4차 Invidious 프록시 시도...")
                    script_data = fetch_transcript_from_invidious(video_id, script_lang)
                    if not script_data and script_lang != 'en':
                        script_data = fetch_transcript_from_invidious(video_id, 'en')
                        if script_data:
                            warn_list.append(f"'{lang_names.get(script_lang, script_lang)}' 자막 없음 — 영어로 대체합니다.")

                if not script_data:
                    raise Exception("자막 추출에 실패했습니다. 유튜브가 봇 접근을 차단했습니다 (429 Rate Limit). 해결하려면 브라우저 확장 프로그램(Learner Pro) 아이콘을 유튜브 동영상 페이지에서 클릭해 실행하거나, 브라우저에서 쿠키를 추출해 프로젝트 폴더 안에 'cookies.txt' 파일로 저장한 후 다시 시도해주세요.")

                # dict_data fallback (script_data가 성공했을 때)
                if not dict_data:
                    dict_data = fetch_transcript_without_cookies(video_id, dict_lang)
                if not dict_data:
                    dict_data = fetch_transcript_via_innertube(video_id, dict_lang)
                if not dict_data:
                    dict_data = fetch_transcript_from_invidious(video_id, dict_lang)
                if not dict_data:
                    dict_lang_name = lang_names.get(dict_lang, dict_lang)
                    warn_list.append(f"'{dict_lang_name}' 해석을 가져올 수 없어 A/ 줄이 비어 있습니다.")

                mock_transcript = build_transcript_response(script_data, dict_data, warn_list)

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()

                response_body = {
                    "warnings": warn_list,
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
            super().do_GET()

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        if parsed_path.path == '/api/submit_transcript':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                video_id = data.get('videoId')
                transcripts = data.get('transcripts', [])
                
                if not video_id:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "Missing videoId"}).encode('utf-8'))
                    return
                
                # 디렉토리 캐시 저장용 경로 생성
                cache_dir = os.path.join(os.path.dirname(__file__), '.cache', 'transcripts')
                os.makedirs(cache_dir, exist_ok=True)

                for item in transcripts:
                    lang = item.get('lang')
                    caption_json = item.get('captionJson')
                    if lang and caption_json:
                        # 캐시 폴더에 원본 JSON 저장
                        cache_file = os.path.join(cache_dir, f"{video_id}_{lang}.json")
                        with open(cache_file, 'w', encoding='utf-8') as f:
                            json.dump(caption_json, f, ensure_ascii=False)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not Found"}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


# Allow address reuse
socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(('0.0.0.0', PORT), TranscriptRequestHandler) as httpd:
    print(f"Serving API and static files at port {PORT}")
    httpd.serve_forever()
