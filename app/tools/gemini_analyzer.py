import os
import re
import json
import asyncio
import vertexai
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

async def analyze_comment(comment: str, model) -> dict:
    """단일 댓글을 Gemini로 비동기 분석."""
    if not comment or not comment.strip():
        return {"comment": comment, "reaction": "중립", "comment_keyword": ""}

    prompt = (
        "You are an expert social media analyst who understands subtle nuances, sarcasm, irony, and metaphors in various languages.\n"
        "Read the following social media comment and perform a deep analysis of the user's intent.\n"
        "Respond ONLY in the JSON format below. Do NOT use markdown formatting like ```json ... ```.\n"
        '{"reaction": "positive or negative or neutral", "comment_keyword": "keyword1, keyword2"}\n\n'
        "Guidelines:\n"
        "- 'reaction': Analyze the sentiment carefully. Be mindful of sarcasm and metaphors.\n"
        "  Must be exactly one of: 'positive', 'negative', or 'neutral'.\n"
        "- 'comment_keyword': Extract 1 to 3 core keywords that represent the main topic or emotion.\n"
        "- DO NOT include any introductory text or explanation outside the JSON.\n\n"
        f"Comment: {comment}"
    )

    try:
        from google.genai.types import GenerateContentConfig
        response = await asyncio.to_thread(
            model.models.generate_content,
            model="gemini-3.1-pro-preview",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=1.0),
        )
        raw_text = response.text.strip()
        
        # 1. thinking 모델의 <thinking>...</thinking> 블록 제거
        clean_text = re.sub(r"<thinking>.*?</thinking>", "", raw_text, flags=re.DOTALL).strip()
        # 2. 마크다운 코드 블록 제거
        clean_text = re.sub(r"```(?:json)?", "", clean_text).replace("```", "").strip()
        # 3. JSON 객체 {}만 정확히 뽑아내기
        json_match = re.search(r"\{.*?\}", clean_text, flags=re.DOTALL)
        if not json_match:
            return {"comment": comment, "reaction": "중립", "comment_keyword": ""}
        
        result_json = json.loads(json_match.group())
        raw_reaction = result_json.get("reaction", "neutral").lower()

        # English to Korean mapping
        reaction_map = {
            "positive": "긍정",
            "negative": "부정",
            "neutral": "중립"
        }
        reaction = reaction_map.get(raw_reaction, "중립")

        return {
            "comment": comment,
            "reaction": reaction,
            "comment_keyword": result_json.get("comment_keyword", ""),
        }
    except Exception as e:
        print(f"⚠️ Gemini 분석 에러: {e}")
        return {"comment": comment, "reaction": "중립", "comment_keyword": ""}


async def analyze_comments_with_gemini(comments_list: list[str]) -> list[dict]:
    """
    댓글 목록을 Gemini API로 분석하여 감성(reaction)과 핵심 키워드(comment_keyword)를 추출합니다.
    GCS 업로드 직전에 scout_tool에서 호출됩니다.

    Args:
        comments_list: 원본 댓글 문자열 목록

    Returns:
        [{"comment": str, "reaction": str, "comment_keyword": str}, ...]
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT or GCP_PROJECT is missing. Run 'make setup-env' first.")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    vertexai.init(project=project_id, location=location)

    # genai Client는 모델(3.1 pro preview)이 있는 global 위치를 명시적으로 사용해야 함
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"
    )

    # 빈 댓글 제외 후, 병렬 분석 실행
    tasks = [analyze_comment(c, client) for c in comments_list if c and c.strip()]
    results = await asyncio.gather(*tasks)

    print(f"📝 [Gemini Analyzer] 댓글 {len(results)}개 분석 완료")
    return list(results)



async def analyze_video_content(video_url: str) -> str:
    """
    영상 URL(GCS 경로 추천)을 입력받아 Vertex AI Gemini를 통해 영상 구조와 대사를 상세 분석합니다.
    """
    # 1. 환경 변수에서 프로젝트 정보 가져오기
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

    if not project_id:
        return "⚠️ 영상 분석 에러: GOOGLE_CLOUD_PROJECT 환경 변수가 설정되지 않았습니다."

    # 2. Vertex AI 초기화 및 클라이언트 생성
    # vertexai=True 설정을 통해 GCP 모드로 동작하게 합니다.
    client = genai.Client(
        vertexai=True,
        project=project_id,
        location=os.environ.get("GOOGLE_CLOUD_LOCATION") or "global"
    )

    prompt = """
    Analyze the audio of the provided video from start to finish and extract it as text.
    Do not include any visual information (screen descriptions, subtitles, etc.) or metadata such as the video title. Focus strictly on the 'timestamp' and 'audio/speech' content.
    
    Please follow these guidelines strictly:
    
    1. Timestamp Analysis: Divide the video chronologically and explicitly label the timestamps (e.g., 01:15 - 02:30) for each segment.
    2. Audio and Speech: For each timestamp segment, document the speaker's core message, product review details, and important dialogue in detail, as if writing a transcript.
    
    [IMPORTANT] Absolutely DO NOT include any introductory phrasing, greetings, or meta commentary. Output ONLY the analytical result data directly.
    """

    try:
        # 3. 모델 호출 (Vertex AI 엔드포인트 사용)
        # vertexai=True일 경우 모델명 앞에 'publishers/google/models/'는 생략 가능합니다.
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-3.1-pro-preview",
            contents=[
                types.Part.from_uri(file_uri=video_url, mime_type='video/mp4'),
                prompt,
            ]
        )
        return response.text
    except Exception as e:
        print(f"⚠️ [Vertex AI Analyzer] 영상 분석 오류: {e}")
        return None