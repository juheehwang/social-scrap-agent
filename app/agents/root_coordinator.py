import os
import vertexai
from google.adk.agents import Agent
from google.adk.models.google_llm import Gemini
from google.adk.tools.agent_tool import AgentTool
from app.tools.scout_tool import scrap_and_upload
from app.agents.data_engineering import get_data_engineering_agent
from app.agents.analytics import get_analytics_agent

def get_root_agent() -> Agent:
    # 0. Vertex AI 환경 초기화
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT or GCP_PROJECT is missing. Run 'make setup-env' first.")
    location = os.getenv("GOOGLE_CLOUD_LOCATION") or "global"
    vertexai.init(project=project_id, location=location)

    # 1. 하위 에이전트 인스턴스화
    data_eng_agent = get_data_engineering_agent()
    analytics_agent = get_analytics_agent()
    
    # 2. 루트 오케스트레이터(Coordinator) 생성
    return Agent(
        name="root_coordinator",
        # gemini-3.1-pro-preview 모델 사용
        model=Gemini(model="gemini-3.1-pro-preview"), 
        description="Coordinator that oversees the full social data pipeline (collection, loading, and analysis). ",
        instruction=(
            "You are a coordinator that oversees the full social data pipeline (collection, loading, and analysis). "
            "Follow the steps below strictly, one at a time:\n\n"
            
            "1. Data Collection Phase:\n"
            "   - Extract `keyword` and `limit` from the user's request and call the 'scrap_and_upload' tool first.\n"
            "   - Wait until the tool finishes. **Do NOT output a collection result message to the user yet** (you must complete loading first).\n\n"
            
            "2. Data Loading Phase (triggered automatically right after successful collection):\n"
            "   - Once 'scrap_and_upload' returns success, extract the GCS URI from the result (e.g., 'gs://bucket/reports/YYYY-MM-DD/xxxxxxxx') and immediately call `data_engineering_agent` WITHOUT talking to the user.\n"
            "   - You MUST pass the exact GCS URI string returned by 'scrap_and_upload' to `data_engineering_agent` as gcs_uri. Also pass today's date as date_str.\n"
            "   - NEVER call `data_engineering_agent` without the exact gcs_uri from the previous step.\n"
            "   - Wait until `data_engineering_agent` finishes completely.\n\n"
            
            "3. Final Report & Analysis Suggestion (after ALL tasks are complete):\n"
            "   - Only AFTER both collection and loading succeed, report the full results (# items collected, table load status) to the user in the same language as the user's request (English or Korean).\n"
            "   - After the report, use `analytics_agent` to suggest possible analysis queries as example questions in the same language as the user's request (English or Korean).\n\n"
            
            "4. For data analysis, chart, platform share, or insight requests:\n"
            "   - Immediately call `analytics_agent`.\n"
            "   - **[Bypass Rule]** Pass the `analytics_agent`'s results to the user exactly as-is without modification.\n\n"
            
            "Core rule: After 'scrap_and_upload' completes, you must NEVER stop and output text to the user. "
            "Always immediately call `data_engineering_agent` with both 'date_str' AND the exact 'gcs_uri' extracted from scrap_and_upload's result, "
            "to complete the full pipeline before reporting results."
        ),
        tools=[
            AgentTool(agent=data_eng_agent),
            AgentTool(agent=analytics_agent),
            scrap_and_upload
        ]
    )