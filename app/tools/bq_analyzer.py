import os
import json
from google.cloud import bigquery
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def execute_bq_query(query: str) -> str:
    """
    BigQuery에서 SQL 쿼리를 실행하고 결과를 Markdown 표 형식으로 반환합니다.
    
    이 툴은 analytics_agent가 사용자의 자연어 질문을 기반으로 작성한
    BigQuery SQL을 실행하고 결과 데이터를 반환하기 위해 사용됩니다.
    
    Args:
        query (str): 실행할 BigQuery 표준 SQL 쿼리문
                     (예: SELECT platform, COUNT(*) as cnt FROM `project.dataset.table` GROUP BY platform ORDER BY cnt DESC LIMIT 10)
                     
    Returns:
        str: Markdown 표 형식의 쿼리 결과 또는 에러 메시지
    """
    print(f"🔍 [BQ Analyzer] 쿼리 실행:\\n{query}")
    
    try:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or "my-youtube-scraper-489216"
        client = bigquery.Client(project=project_id)
        query_job = client.query(query)
        results = query_job.result()
        
        rows = [dict(row.items()) for row in results]
        
        if not rows:
            return "✅ 쿼리는 성공적으로 실행되었으나, 조건에 일치하는 데이터가 없습니다."
        
        print(f"📊 [BQ Analyzer] 쿼리 완료. 총 {len(rows)}건의 결과 확보.")
        
        # Markdown 표(Table) 형식으로 포맷
        headers = list(rows[0].keys())
        
        # 헤더 행
        header_row = "| " + " | ".join(str(h) for h in headers) + " |"
        # 구분선
        separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        # 데이터 행
        data_rows = []
        for row in rows:
            row_values = []
            for h in headers:
                val = row.get(h, "")
                # 숫자형이면 포맷 처리
                if isinstance(val, float):
                    val = f"{val:,.2f}"
                elif isinstance(val, int):
                    val = f"{val:,}"
                row_values.append(str(val))
            data_rows.append("| " + " | ".join(row_values) + " |")
        
        markdown_table = "\n".join([header_row, separator_row] + data_rows)
        
        return f"## 📊 쿼리 결과 ({len(rows)}건)\n\n{markdown_table}"
        
    except Exception as e:
        error_msg = f"❌ 쿼리 실행 중 오류 발생: {str(e)}"
        print(error_msg)
        return error_msg
