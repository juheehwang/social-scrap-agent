import os
import re
import json
import urllib.parse
import io
import base64
import matplotlib.pyplot as plt
import platform
import logging
from google.cloud import bigquery
from google import genai
from google.genai.types import GenerateContentConfig
from dotenv import load_dotenv

load_dotenv()


def generate_markdown_table(rows: list) -> str:
    """수동으로 마크다운 테이블 포맷팅을 생성합니다 (tabulate 의존성 없이 실행)."""
    if not rows:
        return ""
        
    cols = list(rows[0].keys())
    
    # Header
    markdown = "| " + " | ".join(cols) + " |\n"
    markdown += "| " + " | ".join(["---"] * len(cols)) + " |\n"
    
    # Body
    for row in rows:
        formatted_row = []
        for col in cols:
            val = row.get(col, "")
            if isinstance(val, (int, float)):
                formatted_row.append(f"{val:,}") # comma formatting
            else:
                # Sanitize text to prevent pipes (|) and newlines from breaking markdown table syntax
                clean_text = str(val).replace("|", "-").replace("\n", " ").strip()
                formatted_row.append(clean_text)
        markdown += "| " + " | ".join(formatted_row) + " |\n"
        
    return markdown


def execute_direct_bigquery_sql(query: str) -> str:
    """
    빅쿼리에 대한 표준 SQL 조회를 직접 수행하고, 데이터 표 및 차트를 자동 렌더링합니다. (403 권한 에러 우회)
    이 버전은 COUNT 쿼리를 먼저 실행하여 데이터 정합성을 검증합니다.
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT or GCP_PROJECT is missing. Run 'make setup-env' first.")
    dataset_id = os.environ.get("BQ_DATASET_ID", "social_dataset")
    
    client = genai.Client(vertexai=True, project=project_id, location="us-central1")
    bq_client = bigquery.Client(project=project_id)

    # 1. Count 쿼리 생성 프롬프트
    count_sys_prompt = f"""
You are an expert BigQuery SQL engineer. Convert the user's natural language question into a SQL query that ONLY COUNTS the number of matching rows.
The result must be a single row with a single column (e.g., `COUNT(*)` or `COUNT(1)`).

The dataset is `{project_id}.{dataset_id}`.
Tables:
1. `daily_social_scrap` (Parent)
2. `social_comment` (Child)

Join rules:
- Inner join on `scrap_id` when combining post and comments.

Examples:
Q: '명품화장품' 키워드 영상 목록 보여줘
A: SELECT COUNT(*) FROM `daily_social_scrap` WHERE keyword = '명품화장품'

Return ONLY the SQL query. No markdown, no triple backticks, no comments.
"""

    # 2. Data 쿼리 생성 프롬프트
    data_sys_prompt = f"""
You are an expert BigQuery SQL engineer. Convert the user's natural language question into a clean, running Google BigQuery Standard SQL query.

The dataset is `{project_id}.{dataset_id}`.
Tables:
1. `daily_social_scrap` (Parent)
2. `social_comment` (Child)

Join rules:
- Inner join on `scrap_id` when combining post and comments.

Return ONLY the SQL query. No markdown, no triple backticks, no comments.
"""

    # --- Step 1: Count 쿼리 생성 및 실행 ---
    try:
        count_response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=query,
            config=GenerateContentConfig(
                system_instruction=count_sys_prompt,
                temperature=0.1
            )
        )
        count_sql = count_response.text.strip()
        count_sql = re.sub(r"```(?:sql)?", "", count_sql).replace("```", "").strip()
    except Exception as e:
        return f"❌ Count SQL 유추 도중 오류가 발생했습니다: {str(e)}"

    expected_count = -1
    is_aggregate_query = False

    try:
        count_job = bq_client.query(count_sql)
        count_results = count_job.result()
        for row in count_results:
            expected_count = list(row.values())[0]
            break
    except Exception as e:
        logging.warning(f"Count query failed or not applicable: {e}")
        is_aggregate_query = True


    # --- Step 2: Data 쿼리 생성 및 실행 ---
    def generate_and_run_data_sql(feedback_prompt=None):
        prompt = query
        if feedback_prompt:
            prompt = feedback_prompt

        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=prompt,
            config=GenerateContentConfig(
                system_instruction=data_sys_prompt,
                temperature=0.1
            )
        )
        sql = response.text.strip()
        sql = re.sub(r"```(?:sql)?", "", sql).replace("```", "").strip()
        
        query_job = bq_client.query(sql)
        results = query_job.result()
        rows = [dict(r.items()) for r in results]
        return sql, rows

    try:
        sql_generated, data_rows = generate_and_run_data_sql()
    except Exception as e:
        if 'sql_generated' in locals():
            return f"❌ Data 쿼리 실행 오류가 발생했습니다.\n- 생성된 SQL:\n```sql\n{sql_generated}\n```\n- 오류 상세:\n{str(e)}"
        else:
            return f"❌ Data 쿼리 실행 오류가 발생했습니다.\n- 오류 상세:\n{str(e)}"

    # --- Step 3: 검증 및 재시도 ---
    if not is_aggregate_query and expected_count >= 0:
        actual_count = len(data_rows)
        if actual_count != expected_count:
            # 재시도 프롬프트 작성
            retry_prompt = (
                f"사용자 질문: {query}\n\n"
                f"이전 생성된 SQL: {sql_generated}\n"
                f"예상 데이터 건수(COUNT): {expected_count}\n"
                f"실제 조회 건수: {actual_count}\n\n"
                f"위 정보는 불일치합니다. 조인 조건이나 필터링을 확인하여 예상 건수({expected_count})와 일치하도록 SQL을 다시 작성해 주세요."
            )
            try:
                sql_generated, data_rows = generate_and_run_data_sql(retry_prompt)
            except Exception as e:
                logging.warning(f"Retry query failed: {e}")

    # 결과 표 생성
    if not data_rows:
        return (
            f"✅ 테이블 조회는 성공했으나, 조건과 일치하는 데이터가 0건입니다.\n\n"
            f"- **실행된 SQL:**\n```sql\n{sql_generated}\n```"
        )

    md_table = generate_markdown_table(data_rows)
    
    output = []
    output.append("📊 **빅쿼리 조회 결과 데이터 표**\n")
    output.append(md_table)
    if not is_aggregate_query and expected_count >= 0 and len(data_rows) != expected_count:
        output.append(f"\n⚠️ **주의**: 예상 건수({expected_count}건)와 실제 조회 건수({len(data_rows)}건)가 일치하지 않습니다. (재시도 후에도 불일치)")
    output.append("\n- **실행된 SQL:**\n```sql\n" + sql_generated + "\n```")
        
    return "\n".join(output)

