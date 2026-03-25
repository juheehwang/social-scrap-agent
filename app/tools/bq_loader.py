import os
import time
from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()

def load_daily_report_to_bigquery(date_str: str) -> str:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or "my-youtube-scraper-489216"
    dataset_id = os.getenv("BQ_DATASET_ID") or "social_dataset"
    bucket_name = "scrap_social_data" # URI에서 확인된 버킷명으로 하드코딩
    
    parent_table_id = f"{project_id}.{dataset_id}.daily_social_scrap"
    child_table_id = f"{project_id}.{dataset_id}.social_comment"
    
    safe_date_str = date_str.replace("-", "")
    unique_timestamp = int(time.time())
    temp_table_id = f"{project_id}.{dataset_id}.temp_raw_data_{safe_date_str}_{unique_timestamp}"
    
    # 🚨 [가장 중요한 수정] 보여주신 URI에 맞춰 .json 확장자 제거!
    gcs_uri = f"gs://{bucket_name}/reports/{date_str}" 
    
    client = bigquery.Client(project=project_id)

    try:
        # --- [STEP 1] 예전 코드처럼 autodetect=True를 사용하여 단순하게 로드 ---
        job_config = bigquery.LoadJobConfig(
            autodetect=True,
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
            ignore_unknown_values=True
        )
        
        print(f"\n[{date_str}] 임시 테이블에 GCS 데이터({gcs_uri}) 로드 중...")
        load_job = client.load_table_from_uri(gcs_uri, temp_table_id, job_config=job_config)
        load_job.result()
        
        if load_job.output_rows == 0:
            return f"⚠️ 실패: GCS에서 데이터를 1건도 읽지 못했습니다."

        print(f"✅ GCS에서 총 {load_job.output_rows}건 로드 완료!")

        # --- [STEP 2] 부모 테이블 MERGE (조회수/댓글수 업데이트) ---
        parent_merge_query = f"""
        MERGE `{parent_table_id}` T
        USING (
          SELECT 
            CAST(FARM_FINGERPRINT(url) AS STRING) AS scrap_id,
            keyword, url, title, platform, owner, published_at, views, comment_count
          FROM `{temp_table_id}`
        ) S
        ON T.scrap_id = S.scrap_id
        WHEN MATCHED THEN
          UPDATE SET views = S.views, comment_count = S.comment_count
        WHEN NOT MATCHED THEN
          INSERT (scrap_id, keyword, url, title, platform, owner, published_at, views, comment_count)
          VALUES (S.scrap_id, S.keyword, S.url, S.title, S.platform, S.owner, S.published_at, S.views, S.comment_count)
        """
        parent_job = client.query(parent_merge_query)
        parent_job.result()
        print(f"✅ 부모 테이블: {parent_job.num_dml_affected_rows}건 업데이트/적재 완료.")

        # --- [STEP 3] 자식 테이블 MERGE (파이썬이 분석한 analyzed_comments 사용) ---
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
          WHERE ac.comment IS NOT NULL AND TRIM(ac.comment) != ''
        ) S
        ON T.scrap_id = S.scrap_id AND T.comment = S.comment
        WHEN NOT MATCHED THEN
          INSERT (scrap_id, comment, reaction, comment_keyword) 
          VALUES (S.scrap_id, S.comment, S.reaction, S.comment_keyword)
        """
        child_job = client.query(child_merge_query)
        child_job.result()     
        print(f"✅ 자식 테이블: {child_job.num_dml_affected_rows}건 (새로운 댓글) 적재 완료.")

        return f"SUCCESS: BigQuery 적재 성공 (부모: {parent_job.num_dml_affected_rows}건, 자식: {child_job.num_dml_affected_rows}건)"

    except Exception as e:
        return f"ERROR: 데이터 적재 중 오류 발생 - {str(e)}"
        
    finally:
        print(f"비용 절감을 위해 임시 테이블({temp_table_id}) 파기 중...")
        client.delete_table(temp_table_id, not_found_ok=True)