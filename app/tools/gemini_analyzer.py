import os
import re
import json
import asyncio
from dotenv import load_dotenv

load_dotenv()

async def analyze_comment(comment: str, model) -> dict:
    """단일 댓글을 Gemini로 비동기 분석."""
    if not comment or not comment.strip():
        return {"comment": comment, "reaction": "중립", "comment_keyword": ""}

    prompt = (
        "Read the following social media comment and analyze it.\n"
        "Respond ONLY in the following JSON format. Do NOT use markdown symbols (```).\n"
        '{\"reaction\": \"긍정 or 부정 or 중립\", \"comment_keyword\": \"keyword1, keyword2\"}\n\n'
        "Rule 1: 'reaction' must be exactly one of: '긍정' (positive), '부정' (negative), or '중립' (neutral). Write it in Korean.\n"
        "Rule 2: 'comment_keyword' must contain 1 to 3 core keywords extracted from the comment, separated by commas. Write keywords in Korean.\n"
        "Rule 3: Do not add any explanation or extra text outside the JSON.\n\n"
        f"Comment: {comment}"
    )

    try:
        from google.genai.types import GenerateContentConfig
        response = await asyncio.to_thread(
            model.models.generate_content,
            model="gemini-3.1-pro-preview",
            contents=prompt,
            config=GenerateContentConfig(temperature=1),  # thinking 모델은 temperature=1 필요
        )
        raw_text = response.text.strip()
        
        # 1. thinking 모델의 <thinking>...</thinking> 블록 제거
        clean_text = re.sub(r"<thinking>.*?</thinking>", "", raw_text, flags=re.DOTALL).strip()
        # 2. 마크다운 코드 블록 제거
        clean_text = re.sub(r"```(?:json)?", "", clean_text).replace("```", "").strip()
        # 3. JSON 객체 {}만 정확히 뽑아내기 (앞뒤 불필요한 텍스트 제거)
        json_match = re.search(r"\{.*?\}", clean_text, flags=re.DOTALL)
        if not json_match:
            print(f"⚠️ JSON을 찾을 수 없음. 응답: {raw_text[:200]}")
            return {"comment": comment, "reaction": "중립", "comment_keyword": ""}
        
        result_json = json.loads(json_match.group())
        reaction = result_json.get("reaction", "중립")
        # reaction 값 유효성 검증
        if reaction not in ("긍정", "부정", "중립"):
            reaction = "중립"
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
    import vertexai
    from google import genai

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "my-youtube-scraper-489216")
    # Gemini 2.5 Flash는 global 엔드포인트에서만 접근 가능
    vertexai.init(project=project_id, location="global")

    client = genai.Client(vertexai=True)

    # 빈 댓글 제외 후, 병렬 분석 실행
    tasks = [analyze_comment(c, client) for c in comments_list if c and c.strip()]
    results = await asyncio.gather(*tasks)

    print(f"📝 [Gemini Analyzer] 댓글 {len(results)}개 분석 완료")
    return list(results)
