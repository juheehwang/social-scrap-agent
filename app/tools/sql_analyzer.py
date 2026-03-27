import os
import re
import json
import urllib.parse
import io
import base64
import matplotlib.pyplot as plt
import platform
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
    
    Args:
        query (str): 사용자의 자연어 질문
        
    Returns:
        str: 표준 SQL 생성 내역, 데이터 마크다운 표, 차트 이미지 주소가 포함된 출력물
    """
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "my-youtube-scraper-489216")
    dataset_id = os.environ.get("BQ_DATASET_ID", "social_dataset")
    
    # 1. 자연어 → ANSI SQL로 변환 (Gemini Flash 사용)
    # 툴 내에서 Gemini Client를 생성하여 SQL만 직접 유추하게 만듭니다.
    # Vertex AI Reasoning Engine(에이전트 클라우드 런타임) 안에서 standard genai.Client()는 기본 작동합니다.
    client = genai.Client() # Service account auth by default
    
    sys_prompt = f"""
You are a expert BigQuery SQL engineer. Convert the user's natural language question into a clean, running Google BigQuery Standard SQL query.

The dataset is `{project_id}.{dataset_id}`.
There are two tables:

1. `daily_social_scrap` (Parent)
   - scrap_id: STRING (Unique ID)
   - keyword: STRING
   - url: STRING
   - title: STRING
   - platform: STRING
   - owner: STRING
   - views: INT64
   - comment_count: INT64

2. `social_comment` (Child)
   - scrap_id: STRING (Foreign key to daily_social_scrap)
   - comment: STRING
   - reaction: STRING (Categorical: '긍정', '부정', '중립' in Korean)
   - comment_keyword: STRING

Join rules:
- Inner join on `scrap_id` when combining post and comments.
- Grouping on emotions ('긍정', '부정') or keyword is highly encouraged.

Few-shot Examples:

Q: '명품화장품' 키워드로 수집된 영상들의 실제 댓글 총 개수는?
A:
SELECT COUNT(c.comment) AS total_comments
FROM `daily_social_scrap` s
JOIN `social_comment` c ON s.scrap_id = c.scrap_id
WHERE s.keyword = '명품화장품'

Q: 가장 조회수가 높은 영상 5개의 제목과 조회수는?
A:
SELECT title, views
FROM `daily_social_scrap`
ORDER BY views DESC
LIMIT 5

Q: '메이크업'이 포함된 키워드 영상들의 긍정 댓글 비율은?
A:
SELECT c.reaction, COUNT(*) as cnt
FROM `daily_social_scrap` s
JOIN `social_comment` c ON s.scrap_id = c.scrap_id
WHERE s.keyword LIKE '%메이크업%'
GROUP BY c.reaction

Return ONLY the SQL query. No markdown, no triple backticks, no comments.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.1-pro-preview",
            contents=query,
            config=GenerateContentConfig(
                system_instruction=sys_prompt,
                temperature=0.1 # Deterministic SQL
            )
        )
        sql_generated = response.text.strip()
        # Clean background markdown if any
        sql_generated = re.sub(r"```(?:sql)?", "", sql_generated).replace("```", "").strip()
    except Exception as e:
        return f"❌ SQL 유추 도중 오류가 발생했습니다: {str(e)}"

    # 2. BigQuery 조회 실행
    bq_client = bigquery.Client(project=project_id)
    
    try:
        query_job = bq_client.query(sql_generated)
        results = query_job.result()
        
        data_rows = []
        for row in results:
            data_rows.append(dict(row.items()))
    except Exception as e:
        # Fallback if generated SQL is invalid
        return f"❌ BigQuery 실행 오류가 발생했습니다.\n- 생성된 SQL:\n```sql\n{sql_generated}\n```\n- 오류 상세:\n{str(e)}"


    if not data_rows:
        return (
            f"✅ 테이블 조회는 성공했으나, 조건과 일치하는 데이터가 0건입니다.\n\n"
            f"- **실행된 SQL:**\n```sql\n{sql_generated}\n```"
        )

    # 3. 표 가공
    md_table = generate_markdown_table(data_rows)
    
    output = []
    output.append("📊 **빅쿼리 조회 결과 데이터 표**\n")
    output.append(md_table)
    output.append("\n- **실행된 SQL:**\n```sql\n" + sql_generated + "\n```")
        
    return "\n".join(output)
