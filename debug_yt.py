try:
    import youtube_transcript_api
    from youtube_transcript_api import YouTubeTranscriptApi
    print(f"Version: {getattr(youtube_transcript_api, '__version__', 'unknown')}")
    print(f"Attributes: {dir(YouTubeTranscriptApi)}")
    # Test a call
    # YouTubeTranscriptApi.get_transcript('dQw4w9WgXcQ') 
except Exception as e:
    print(f"Error: {e}")
