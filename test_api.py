from youtube_transcript_api import YouTubeTranscriptApi
video_id = "7NLzd2mjz-g"
try:
    print("Testing YouTubeTranscriptApi.list_transcripts(video_id)")
    tl = YouTubeTranscriptApi.list_transcripts(video_id)
    print("Success classmethod:", tl)
except Exception as e:
    print("Failed classmethod:", e)

try:
    print("Testing YouTubeTranscriptApi().list(video_id)")
    tl = YouTubeTranscriptApi().list(video_id)
    print("Success instance method:", tl)
except Exception as e:
    print("Failed instance method:", e)

