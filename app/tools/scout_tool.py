import asyncio
import os
import json
from datetime import datetime
from app.tools.youtube_api import YouTubeScraperAPI
from app.tools.gcs_uploader import GCSUploader

async def scrap_and_upload(keyword: str, limit: int = 5) -> str:
    """
    YouTube 데이터를 수집하고 GCS에 업로드합니다.

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

    # 2. 평탄화(Flatten) 처리
    combined_records = []
    for item in youtube_data:
        record = item.copy()
        record["platform"] = "youtube"
        record["keyword"] = keyword
        
        for key, value in record.items():
            if isinstance(value, list):
                flat_list = []
                for sub_item in value:
                    if isinstance(sub_item, list): flat_list.extend(sub_item)
                    else: flat_list.append(sub_item)
                record[key] = flat_list
        combined_records.append(record)

    # 3. NDJSON 저장 및 업로드
    os.makedirs("reports", exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    report_path = f"reports/{today_str}.json"
    
    with open(report_path, "w", encoding="utf-8") as f:
        for record in combined_records:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")
   
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        return "❌ 실패: GCS_BUCKET_NAME 환경변수가 설정되지 않았습니다."

    uploader = GCSUploader(bucket_name)
    gcs_uri = uploader.upload_daily_report(report_path)
    
    return f"✅ 성공: 데이터를 수집하여 GCS에 업로드했습니다. URI: {gcs_uri}"
