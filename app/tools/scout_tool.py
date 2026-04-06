import asyncio
import os
import json
import uuid
from datetime import datetime
from app.tools.youtube_api import YouTubeScraperAPI
from app.tools.gcs_uploader import GCSUploader
from app.tools.gemini_analyzer import analyze_comments_with_gemini

async def scrap_and_upload(keyword: str, limit: int = 5) -> str:
    """
    YouTube 데이터를 수집하고, Gemini로 댓글을 분석한 뒤 GCS에 업로드합니다.

    Args:
        keyword (str): 수집할 키워드 (예: "봄신상")
        limit (int): 수집 개수 (기본값 5)

    Returns:
        str: 업로드된 GCS URI 또는 에러 메시지
    """
    print(f"🕵️ [Scout Tool] 수집 시작: 키워드='{keyword}', 제한={limit}개")

    # 1. 데이터 수집
    scraper = YouTubeScraperAPI()
    try:
        youtube_data = await asyncio.to_thread(scraper.scrape, keyword, max_results=limit)
    except Exception as e:
        print(f"⚠️ [수집 오류] {e}")
        youtube_data = []

    # 2. 평탄화(Flatten) 처리 및 Gemini 댓글 분석
    combined_records = []
    async def _process_post(item):
        record = item.copy()
        record["platform"] = "youtube"
        record["keyword"] = keyword
        title_snip = record.get("title", "Unknown")[:20]

        print(f"🎬 [Scout Tool] '{title_snip}...' 게시물 처리 시작")

        # 댓글 목록 추출 (flat하게 처리)
        for key, value in record.items():
            if isinstance(value, list):
                flat_list = []
                for sub_item in value:
                    if isinstance(sub_item, list):
                        flat_list.extend(sub_item)
                    else:
                        flat_list.append(sub_item)
                record[key] = flat_list
        
        raw_comments = record.get("comments", [])
        video_url = record.get("url", "")
        
        async def _analyze_comments():
            if raw_comments:
                print(f"📝 [Scout Tool] '{title_snip}...' 댓글 {len(raw_comments)}개 Gemini 분석 중...")
                from app.tools.gemini_analyzer import analyze_comments_with_gemini
                return await analyze_comments_with_gemini(raw_comments)
            return []
            
        async def _analyze_video():
            if video_url:
                print(f"🎬 [Scout Tool] '{title_snip}...' 유튜브 영상 요약 분석 중...")
                from app.tools.gemini_analyzer import analyze_video_content
                return await analyze_video_content(video_url)
            return ""

        # 비동기로 동시에 분석 실행 (댓글 + 영상)
        analyzed_comments, video_analysis = await asyncio.gather(_analyze_comments(), _analyze_video())
        
        record["analyzed_comments"] = analyzed_comments
        record["content"] = video_analysis
        
        print(f"✅ [Scout Tool] '{title_snip}...' 게시물 처리 완료")
        return record

    # 비동기 병렬 처리 실행
    tasks = [_process_post(item) for item in youtube_data]
    combined_records = list(await asyncio.gather(*tasks))

    # 3. NDJSON 저장 및 업로드
    os.makedirs("reports", exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    unique_id = uuid.uuid4().hex[:8]
    report_path = f"reports/{today_str}_{unique_id}.json"

    with open(report_path, "w", encoding="utf-8") as f:
        for record in combined_records:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")

    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        return "❌ 실패: GCS_BUCKET_NAME 환경변수가 설정되지 않았습니다."

    uploader = GCSUploader(bucket_name)
    blob_name = uploader.upload_daily_report(report_path)
    exact_gcs_uri = f"gs://{bucket_name}/{blob_name}"

    return f"✅ 성공: 데이터 {len(combined_records)}개 수집 및 Gemini 분석 완료 후 GCS에 업로드했습니다. URI: {exact_gcs_uri}"
