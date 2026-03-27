import os
import time
from dotenv import load_dotenv
from google.cloud import bigquery

# .env 파일 로드
load_dotenv()

def load_daily_report_to_bigquery(date_str: str) -> str:
    """
    GCS에서 Gemini 분석이 완료된 NDJSON 파일을 BigQuery에 적재합니다.
    
    1. 게시물 원본 정보는 부모 테이블(daily_social_scrap)에 MERGE 적재
    2. 분석된 댓글 데이터는 자식 테이블(social_comment)에 MERGE 적재
    (댓글 감성/키워드는 이미 GCS 업로드 전에 Gemini가 Python에서 분석 완료)
    """
    
    # 1. 환경변수 및 기본 설정
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or "my-youtube-scraper-489216"
    dataset_id = os.getenv("BQ_DATASET_ID") or "social_dataset"
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    
    parent_table_name = os.getenv("BQ_TABLE_NAME", "daily_social_scrap")
    child_table_name = "social_comment"
    
    parent_table_id = f"{project_id}.{dataset_id}.{parent_table_name}"
    child_table_id = f"{project_id}.{dataset_id}.{child_table_name}"
    
    # 충돌 방지를 위해 임시 테이블 이름에 타임스탬프 추가
    safe_date_str = date_str.replace("-", "")
    unique_timestamp = int(time.time())
    temp_table_id = f"{project_id}.{dataset_id}.temp_raw_data_{safe_date_str}_{unique_timestamp}"
    
    # GCS URI
    gcs_uri = f"gs://{bucket_name}/reports/{date_str}"

    client = bigquery.Client(project=project_id)

    try:
        # Schema definitions to prevent auto-detect from converting empty arrays to STRING
        schema = [
            bigquery.SchemaField("keyword", "STRING"),
            bigquery.SchemaField("url", "STRING"),
            bigquery.SchemaField("title", "STRING"),
            bigquery.SchemaField("platform", "STRING"),
            bigquery.SchemaField("owner", "STRING"),
            bigquery.SchemaField("published_at", "TIMESTAMP"),
            bigquery.SchemaField("views", "INT64"),
            bigquery.SchemaField("comment_count", "INT64"),
            bigquery.SchemaField("comments", "STRING", mode="REPEATED"),
            bigquery.SchemaField(
                "analyzed_comments",
                "RECORD",
                mode="REPEATED",
                fields=[
                    bigquery.SchemaField("comment", "STRING"),
                    bigquery.SchemaField("reaction", "STRING"),
                    bigquery.SchemaField("comment_keyword", "STRING"),
                ],
            ),
        ]
        
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            ignore_unknown_values=True
        )
        
        print(f"[{date_str}] 임시 테이블({temp_table_id})에 Raw 데이터 로드 중...")
        load_job = client.load_table_from_uri(gcs_uri, temp_table_id, job_config=job_config)
        load_job.result()
        
        # --- [STEP 2] 부모 테이블(원본 게시물)에 데이터 MERGE ---
        parent_merge_query = f"""
        MERGE `{parent_table_id}` T
        USING (
          SELECT 
            CAST(FARM_FINGERPRINT(url) AS STRING) AS scrap_id,
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

        # --- [STEP 3] 자식 테이블(Gemini 사전 분석 완료된 댓글) MERGE ---
        # analyzed_comments는 {comment, reaction, comment_keyword} 객체 배열
        child_merge_query = f"""
        MERGE `{child_table_id}` T
        USING (
          SELECT 
            CAST(FARM_FINGERPRINT(url) AS STRING) AS scrap_id,
            ac.comment,
            ac.reaction,
            ac.comment_keyword
          FROM `{temp_table_id}`,
          UNNEST(analyzed_comments) AS ac
          WHERE ac.comment IS NOT NULL AND ac.comment != ''
        ) S
        ON T.scrap_id = S.scrap_id AND T.comment = S.comment
        WHEN NOT MATCHED THEN
          INSERT (scrap_id, comment, reaction, comment_keyword) 
          VALUES (S.scrap_id, S.comment, S.reaction, S.comment_keyword)
        """
        print("자식 테이블(Gemini 분석 댓글) MERGE 적재 실행 중...")
        client.query(child_merge_query).result()
        
        print(f"[{date_str}] 데이터 적재 완료!")
        return f"SUCCESS: {date_str} 데이터가 BigQuery에 성공적으로 적재되었습니다. (게시물: {parent_table_id}, 댓글: {child_table_id})"

    except Exception as e:
        print(f"ERROR: 데이터 적재 중 오류 발생 - {str(e)}")
        return f"ERROR: 데이터 적재 중 오류 발생 - {str(e)}"
        
    finally:
        # --- [STEP 4] 임시 테이블 무조건 삭제 (비용 절감) ---
        print(f"비용 절감을 위해 임시 테이블({temp_table_id}) 파기 중...")
        client.delete_table(temp_table_id, not_found_ok=True)