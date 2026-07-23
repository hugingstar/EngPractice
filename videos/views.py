import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from .youtube_utils import fetch_transcript_via_innertube, fetch_transcript_without_cookies, fetch_transcript_from_invidious, build_transcript_response
from youtube_transcript_api import YouTubeTranscriptApi
from django.conf import settings
from kafka import KafkaProducer

logger = logging.getLogger(__name__)

# Kafka Producer 초기화 (연결 실패 시 무시하도록 예외 처리)
producer = None
try:
    producer = KafkaProducer(
        bootstrap_servers=settings.KAFKA_BROKER_URL,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
except Exception as e:
    logger.warning(f"Kafka Producer 연결 실패: {e}")

@csrf_exempt
def get_video_transcript(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            video_id = data.get('video_id')
            lang = data.get('lang', 'en')

            if not video_id:
                return JsonResponse({"error": "video_id is required"}, status=400)

            # 1. Kafka에 이벤트 발행
            if producer:
                try:
                    event = {
                        "event_type": "transcript_request",
                        "video_id": video_id,
                        "user_id": request.user.username if request.user.is_authenticated else "anonymous",
                    }
                    producer.send('video_requests', value=event)
                except Exception as e:
                    logger.error(f"Kafka 발송 에러: {e}")

            # 2. Redis 캐시 확인
            cache_key = f"transcript_{video_id}_{lang}"
            cached_data = cache.get(cache_key)
            if cached_data:
                return JsonResponse({"source": "redis_cache", "data": cached_data})

            # 3. 자막 가져오기 로직 (youtube_transcript_api 우선 시도)
            transcript_list = None
            try:
                raw_transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[lang])
                transcript_list = [{"text": t['text'], "start": t['start'], "duration": t['duration']} for t in raw_transcript]
            except Exception as e:
                logger.warning(f"youtube_transcript_api 실패: {e}")

            if not transcript_list:
                # 4. Fallback: InnerTube -> HTML -> Invidious
                fetched = fetch_transcript_via_innertube(video_id, lang)
                if not fetched:
                    fetched = fetch_transcript_without_cookies(video_id, lang)
                if not fetched:
                    fetched = fetch_transcript_from_invidious(video_id, lang)

                if fetched:
                    transcript_list = [{"text": t.text, "start": t.start, "duration": t.duration} for t in fetched]

            if transcript_list:
                # Redis에 1시간 캐싱
                cache.set(cache_key, transcript_list, timeout=3600)
                return JsonResponse({"source": "live_fetch", "data": transcript_list})
            else:
                return JsonResponse({"error": "자막을 가져오지 못했습니다."}, status=404)

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method Not Allowed"}, status=405)
