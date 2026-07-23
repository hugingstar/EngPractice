import http.server
import socketserver
import json
import sys
import os

# root 권한으로 실행될 때, 사용자의 로컬 파이썬 패키지를 찾을 수 있도록 경로 추가
user_site_packages = os.path.expanduser('~yusunglee/Library/Python/3.9/lib/python/site-packages')
if user_site_packages not in sys.path:
    sys.path.append(user_site_packages)

import urllib.parse
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

# 전역 Session 생성
global_session = requests.Session()

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

    speaker_emojis = ['🧑', '🧑‍🦰', '🧑‍🦱', '🧑‍🦳', '🧑‍🦲', '👱']
    current_speaker_idx = 0

    for item in grouped_data:
        start = item['start']
        duration = item['duration']

        word_tuples = item['words']
        text = " ".join(t for t, _ in word_tuples)

        target_text = find_closest_dict(start).replace('\n', ' ')

        emoji_to_use = ''
        if '>>' in text or '>>' in target_text:
            emoji_to_use = speaker_emojis[current_speaker_idx % len(speaker_emojis)]
            text = text.replace('>>', emoji_to_use)
            target_text = target_text.replace('>>', emoji_to_use)
            current_speaker_idx += 1

        word_objs = []
        for chunk_text, chunk_start in word_tuples:
            if emoji_to_use and '>>' in chunk_text:
                chunk_text = chunk_text.replace('>>', emoji_to_use)
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

PORT = int(os.environ.get('PORT', 80))


