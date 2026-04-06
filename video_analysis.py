import os
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("🚨 API 키가 없습니다. .env 파일을 확인해주세요.")
    exit()

client = genai.Client(api_key=api_key, vertexai=False)

async def extract_detailed_video_content(video_url: str) -> str | None:
    """
    영상 URL의 음성을 Gemini AI Studio 공식 API로 분석하여 상세 요약 및 트랜스크립트를 생성합니다.
    """
    prompt = """
    Analyze the audio of the provided video from start to finish and extract it as text.
    Do not include any visual information or metadata. Focus strictly on the 'timestamp' and 'audio/speech' content.
    
    1. Timestamp Analysis: Divide the video chronologically and explicitly label the timestamps (e.g., 01:15 - 02:30).
    2. Audio and Speech: Document the speaker's core message, product review details, and important dialogue in detail.
    
    [IMPORTANT] Absolutely DO NOT include any introductory phrasing or greetings. Output ONLY the analytical result data directly.
    """

    try:
        print(f"🤖 [{video_url}] Gemini AI Studio로 음성 분석 중...")
        response = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-3.1-pro-preview',
            contents=[
                types.Part.from_uri(file_uri=video_url, mime_type='video/mp4'),
                prompt,
            ]
        )
        return response.text
    except Exception as e:
        print(f"🚨 분석 오류: {e}")
        return None