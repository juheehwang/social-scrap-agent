import os
import vertexai
from google.adk.agents import Agent
from app.tools.bq_loader import load_daily_report_to_bigquery

# 1. 시스템 환경 변수 강제 설정 (Playground/ADK 필수 설정)
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_CLOUD_PROJECT"] = "my-youtube-scraper-489216"

# 2. Vertex AI 초기화
vertexai.init(
    project=os.environ["GOOGLE_CLOUD_PROJECT"],
    location=os.environ["GOOGLE_CLOUD_LOCATION"]
)

def get_data_engineering_agent() -> Agent:
    return Agent(
        name="data_engineering_agent",
        model="gemini-3.1-pro-preview",
        description="Data engineering agent that automatically loads daily JSON data from GCS into BigQuery",
        instruction=(
            "You are a data engineering expert. "
            "When the user (or a coordinator agent) requests loading data for a specific date (e.g., '2026-03-09' or 'today') into BigQuery, "
            "convert the date into a 'YYYY-MM-DD' string format and use the `load_daily_report_to_bigquery` tool to load the data. "
            "If no date is specified, use today's date. "
            "Once the task is complete, clearly return the tool's result (success/failure and loaded data information) in Korean."
        ),
        tools=[load_daily_report_to_bigquery],
        disallow_transfer_to_peers=True
    )