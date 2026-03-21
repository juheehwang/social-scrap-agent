from google.adk.agents import Agent
from app.tools.bq_loader import load_daily_report_to_bigquery

def get_data_engineering_agent() -> Agent:
    return Agent(
        name="data_engineering_agent",
        model="gemini-2.5-pro",
        description="GCS에서 매일 최신화되는 JSON 데이터를 BigQuery에 자동으로 누적(Append) 적재하는 데이터 엔지니어링 에이전트",
        instruction=(
            "너는 데이터 엔지니어링 전문가야. "
            "사용자(또는 관리자 에이전트)가 특정 날짜(예: '2026-03-09' 또는 '오늘')의 데이터를 BigQuery에 적재해달라고 요청하면, "
            "해당 날짜를 'YYYY-MM-DD' 형식의 문자열로 변환한 뒤 `load_daily_report_to_bigquery` 도구를 사용해서 데이터를 로드해. "
            "만약 날짜를 명시하지 않고 적재를 요청받았다면, 오늘 날짜를 기준으로 실행해. "
            "작업이 완료되면 도구의 실행 결과(성공 여부 및 로드된 정보)를 명확하게 반환해."
        ),
        tools=[load_daily_report_to_bigquery],
        disallow_transfer_to_peers=True  # 다른 서브 에이전트로 작업을 넘기지 않음
    )