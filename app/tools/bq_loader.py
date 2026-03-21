import os
import time
from dotenv import load_dotenv
from google.cloud import bigquery

# .env 파일 로드
load_dotenv()

def load_daily_report_to_bigquery(date_str: str) -> str:
    """
    매일 최신화되는 JSON 파일을 임시 테이블에 적재 후,
    1. 게시물 원본 정보는 부모 테이블(daily_social_scrap)에 적재하고
    2. 댓글 배열은 풀어(UNNEST) AI로 감성 분석 후 자식 테이블(social_comment)에 분리 적재합니다.
    """
    
    # 1. 환경변수 및 기본 설정
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or "my-youtube-scraper-489216"
    dataset_id = os.getenv("BQ_DATASET_ID") or "social_dataset"
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    
    # 타켓 테이블 및 모델 이름 설정
    parent_table_name = os.getenv("BQ_TABLE_NAME", "daily_social_scrap")
    child_table_name = "social_comment" # 기본값 유지 혹은 환경변수 대응 가능
    
    parent_table_id = f"{project_id}.{dataset_id}.{parent_table_name}"
    child_table_id = f"{project_id}.{dataset_id}.{child_table_name}"
    model_id = f"{project_id}.{dataset_id}.sentiment_analyzer" 
    
    # 충돌 방지를 위해 임시 테이블 이름에 타임스탬프 추가
    safe_date_str = date_str.replace("-", "")
    unique_timestamp = int(time.time())
    temp_table_id = f"{project_id}.{dataset_id}.temp_raw_data_{safe_date_str}_{unique_timestamp}"
    
    # GCS URI
    gcs_uri = f"gs://{bucket_name}/reports/{date_str}" 

    client = bigquery.Client(project=project_id)

    try:
        # --- [STEP 1] 임시 테이블에 Raw 데이터 로드 ---
        job_config = bigquery.LoadJobConfig(
            autodetect=True,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
        )
        
        print(f"[{date_str}] 임시 테이블({temp_table_id})에 Raw 데이터 로드 중...")
        load_job = client.load_table_from_uri(gcs_uri, temp_table_id, job_config=job_config)
        load_job.result()
        
        # --- [STEP 2] 부모 테이블(원본 게시물)에 데이터 MERGE ---
        parent_merge_query = f"""
        MERGE `{parent_table_id}` T
        USING (
          SELECT 
            CAST(FARM_FINGERPRINT(url) AS STRING) AS scrap_id, -- URL 기반 고유 ID 생성
            keyword, url, title, platform, owner, published_at, views, comment_count
          FROM `{temp_table_id}`
        ) S
        ON T.scrap_id = S.scrap_id
        WHEN NOT MATCHED THEN
          INSERT (scrap_id, keyword, url, title, platform, owner, published_at, views, comment_count)
          VALUES (S.scrap_id, S.keyword, S.url, S.title, S.platform, S.owner, S.published_at, S.views, S.comment_count)
        """
        print("부모 테이블(원본 데이터) MERGE 적재 실행 중...")
        client.query(parent_merge_query).result()

        # --- [STEP 3] 자식 테이블(댓글 및 AI 분석 결과)에 데이터 MERGE ---
        child_merge_query = f"""
        MERGE `{child_table_id}` T
        USING (
          SELECT 
            CAST(FARM_FINGERPRINT(url) AS STRING) AS scrap_id,
            c AS comment,
            JSON_EXTRACT_SCALAR(
              REPLACE(REPLACE(ml_generate_text_llm_result, '```json', ''), '```', ''), 
              '$.reaction'
            ) AS reaction,
            JSON_EXTRACT_SCALAR(
              REPLACE(REPLACE(ml_generate_text_llm_result, '```json', ''), '```', ''), 
              '$.comment_keyword'
            ) AS comment_keyword
          FROM ML.GENERATE_TEXT(
            MODEL `{model_id}`,
           (
              SELECT 
                url, c,
                CONCAT(
                  '다음 소셜 미디어 댓글을 읽고 분석해줘. ',
                  -- 🌟 수정 1: 마크다운 금지 유지 및 여러 키워드 예시(키워드1, 키워드2) 추가
                  '오직 다음 JSON 형식으로만 답하고, 마크다운 기호(```)는 절대 사용하지 마: {{"reaction": "긍정/부정/중립", "comment_keyword": "키워드1, 키워드2, 키워드3"}}. ',
                  -- 🌟 수정 2: AI에게 여러 개를 찾을 경우 쉼표로 구분하라고 강력하게 지시
                  '핵심 단어가 여러 개일 경우 반드시 쉼표(,)로 구분해서 모두 추출해줘. ',
                  '댓글: ', c
                ) AS prompt
              FROM `{temp_table_id}`,
              UNNEST(comments) AS c
              WHERE c IS NOT NULL AND c != ''
            ),
            STRUCT(0.1 AS temperature, TRUE AS flatten_json_output)
          )
        ) S
        ON T.scrap_id = S.scrap_id AND T.comment = S.comment
        WHEN NOT MATCHED THEN
          INSERT (scrap_id, comment, reaction, comment_keyword) 
          VALUES (S.scrap_id, S.comment, S.reaction, S.comment_keyword)
        """
        print("자식 테이블(댓글) Gemini ML 분석 및 MERGE 적재 실행 중...")
        client.query(child_merge_query).result()
        
        print(f"[{date_str}] 데이터 분석 및 부모-자식 테이블 분리 적재 완료!")
        return f"SUCCESS: {date_str} 데이터가 BigQuery에 최적화 구조로 성공적으로 적재되었습니다."

    except Exception as e:
        print(f"ERROR: 데이터 적재 중 오류 발생 - {str(e)}")
        return f"ERROR: 데이터 적재 중 오류 발생 - {str(e)}"
        
    finally:
        # --- [STEP 4] 임시 테이블 무조건 삭제 (비용 절감) ---
        print(f"비용 절감을 위해 임시 테이블({temp_table_id}) 파기 중...")
        client.delete_table(temp_table_id, not_found_ok=True)