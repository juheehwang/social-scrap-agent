import os
import json
import asyncio
import re
from datetime import datetime
from pathlib import Path
from google import adk
from google.adk.apps import App

# 0. ADK App 인스턴스 생성 (Reasoning Engine 및 agent_engine_app에서 사용)
def _get_app():
    from .agents.root_coordinator import get_root_agent
    return App(name="app", root_agent=get_root_agent())

app = _get_app()

# 1. 환경 변수 로드
def init_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("❌ 'python-dotenv' 패키지가 설치되지 않았습니다.")
        return

    current_dir = Path(__file__).parent
    env_path = current_dir / ".env"  # .env 파일을 사용하도록 수정

    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        print(f"✅ [시스템] .env 로드 완료: BUCKET_NAME={os.getenv('GCS_BUCKET_NAME')}")
    else:
        print("⚠️ [시스템] .env 파일을 찾을 수 없거나 로드할 수 없습니다.")


async def run_agent_query(user_input: str, session_id: str, runner: adk.Runner):
    """에이전트에게 쿼리를 보내고 최종 답변을 반환합니다."""
    from google.genai import types
    content = types.Content(role="user", parts=[types.Part.from_text(text=user_input)])
    events = runner.run(user_id="admin", session_id=session_id, new_message=content)
    
    response_text = ""
    for event in events:
        if event.is_final_response():
            response_text = "".join([part.text for part in event.content.parts if hasattr(part, 'text') and part.text])
    return response_text

def run_social_analyzer(user_input: str):
    """비대화형 실행 (Reasoning Engine 등에서 사용)"""
    from .agents.root_coordinator import get_root_agent
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from google import adk

    root_agent = get_root_agent()
    session_service = InMemorySessionService() 
    runner = adk.Runner(agent=root_agent, app_name="app", session_service=session_service)
    
    session = asyncio.run(session_service.create_session(app_name="app", user_id="admin"))
    return asyncio.run(run_agent_query(user_input, session.id, runner))

async def run_social_analyzer_interactive():
    """터미널 대화형 실행"""
    from app.agents.root_coordinator import get_root_agent
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from google import adk

    init_env()
    print("\n--- Social Media Agentic Analyzer (Interactive Mode) ---")
    print("명령을 입력해 주세요. (종료하려면 'exit' 또는 'quit' 입력)")
    
    root_agent = get_root_agent()
    session_service = InMemorySessionService() 
    runner = adk.Runner(agent=root_agent, app_name="app", session_service=session_service)
    session = await session_service.create_session(app_name="app", user_id="admin")
    session_id = session.id
    
    while True:
        user_input = input("\n👤 [User]: ").strip()
        if not user_input: continue
        if user_input.lower() in ["exit", "quit", "종료"]: break
            
        print("\n🤖 [Agent]: ", end="", flush=True)
        response = await run_agent_query(user_input, session_id, runner)
        print(f"{response}")

if __name__ == "__main__":
    asyncio.run(run_social_analyzer_interactive())