import os
from google.cloud import bigquery
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def execute_bq_query(query: str) -> str:
    """
    사용자의 질문을 바탕으로 작성된 SQL 쿼리를 BigQuery에서 실행하고,
    그 결과를 자연어로 답변하기 좋게 문자열(JSON/텍스트) 형태로 반환합니다.
    
    Args:
        query (str): 실행할 표준 SQL 쿼리문
                     (예: SELECT platform, COUNT(*) as cnt FROM `project.dataset.table` GROUP BY platform)
                     
    Returns:
        str: 쿼리 실행 결과 로그 (결과 행의 배열 또는 에러 메시지)
    """
    print(f"🔍 [BQ Analyzer] 쿼리 실행을 준비합니다:\n{query}")
    
    try:
        client = bigquery.Client()
        query_job = client.query(query)
        results = query_job.result()
        
        # 결과를 딕셔너리 리스트로 변환하여 에이전트가 이해하기 쉽게 문자열로 반환
        rows = [dict(row.items()) for row in results]
        
        if not rows:
            return "✅ 쿼리는 성공적으로 실행되었으나, 조건에 일치하는 데이터가 없습니다."
            
        print(f"📊 [BQ Analyzer] 쿼리 완료. 총 {len(rows)}건의 결과 확보.")
        return str(rows)
        
    except Exception as e:
        error_msg = f"❌ 쿼리 실행 중 오류 발생: {str(e)}"
        print(error_msg)
        return error_msg
