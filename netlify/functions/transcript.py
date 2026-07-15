import json
import urllib.parse
from youtube_transcript_api import YouTubeTranscriptApi
import re
import traceback

def handler(event, context):
    # Enable CORS for preflight and actual requests
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type',
        'Access-Control-Allow-Methods': 'GET, OPTIONS'
    }

    if event.get('httpMethod') == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': headers,
            'body': ''
        }

    query_params = event.get('queryStringParameters', {})
    if not query_params:
        query_params = {}
        
    video_id = query_params.get('videoId')
    script_lang = query_params.get('scriptLang', 'en')
    dict_lang = query_params.get('dictLang', 'ko')

    if not video_id:
        return {
            'statusCode': 400,
            'headers': headers,
            'body': json.dumps({'error': 'Missing videoId parameter'})
        }

    try:
        # Fetch transcripts
        transcript_list = YouTubeTranscriptApi.list(video_id)

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
                for w in chunk_words:
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

        response_body = {
            "warnings": warnings,
            "transcript": mock_transcript
        }

        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps(response_body, ensure_ascii=False)
        }

    except Exception as e:
        traceback.print_exc()
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }
