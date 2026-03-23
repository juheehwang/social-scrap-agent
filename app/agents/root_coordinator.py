import vertexai
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from app.tools.scout_tool import scrap_and_upload
from app.agents.data_engineering import get_data_engineering_agent
from app.agents.analytics import get_analytics_agent

def get_root_agent() -> Agent:
    # 0. Vertex AI 환경 초기화 (이 코드가 누락되면 404가 뜰 수 있습니다)
    # 아까 확인한 성공 프로젝트와 리전을 명시합니다.
    vertexai.init(project='my-youtube-scraper-489216', location='us-central1')

    # 1. 하위 에이전트 인스턴스화
    data_eng_agent = get_data_engineering_agent()
    analytics_agent = get_analytics_agent()
    
    # 2. 루트 오케스트레이터(Coordinator) 생성
    return Agent(
        name="root_coordinator",
        # [수정 포인트] 3.1-preview 대신 현재 안정적으로 지원되는 모델 사용
        # 만약 1.5-pro도 안 된다면 'gemini-1.5-flash'를 시도해 보세요.
        model="gemini-3.1-pro-preview", 
        description="Coordinator that orchestrates social data collection, loading, and analytics routing",
        instruction=(
            "You are a coordinator that oversees the full social data pipeline (collection, loading, and analysis). "
            "Follow the steps below strictly, one at a time:\n\n"
            
            "1. Data Collection Phase:\n"
            "   - Extract `keyword` and `limit` from the user's request and call the 'scrap_and_upload' tool first.\n"
            "   - Wait until the tool finishes. **Do NOT output a collection result message to the user yet** (you must complete loading first).\n\n"
            
            "2. Data Loading Phase (triggered automatically right after successful collection):\n"
            "   - Once 'scrap_and_upload' returns success, immediately call `data_engineering_agent` WITHOUT talking to the user.\n"
            "   - If no date is specified, instruct `data_engineering_agent` to load using today's date.\n"
            "   - Wait until `data_engineering_agent` finishes completely.\n\n"
            
            "3. Final Report & Analysis Suggestion (after ALL tasks are complete):\n"
            "   - Only AFTER both collection and loading succeed, report the full results (# items collected, table load status) to the user in Korean.\n"
            "   - After the report, use `analytics_agent` to suggest possible analysis queries as example questions in Korean.\n\n"
            
            "4. For data analysis, chart, platform share, or insight requests:\n"
            "   - Immediately call `analytics_agent`.\n"
            "   - **[Bypass Rule]** Pass the `analytics_agent`'s results to the user exactly as-is without modification.\n\n"
            
            "Core rule: After 'scrap_and_upload' completes, you must NEVER stop and output text to the user. "
            "Always immediately call `data_engineering_agent`, which will invoke `load_daily_report_to_bigquery` (defined in app/tools/bq_loader.py), "
            "to complete the full pipeline before reporting results."
        ),
        tools=[
            AgentTool(agent=data_eng_agent),
            AgentTool(agent=analytics_agent),
            scrap_and_upload
        ]
    )