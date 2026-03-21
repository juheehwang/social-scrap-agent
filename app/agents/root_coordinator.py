from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from app.tools.scout_tool import scrap_and_upload
from app.agents.data_engineering import get_data_engineering_agent
from app.agents.analytics import get_analytics_agent

def get_root_agent() -> Agent:
    # 1. 서브 에이전트 인스턴스화
    data_eng_agent = get_data_engineering_agent()
    analytics_agent = get_analytics_agent()
    
    # 2. 루트 오케스트레이터 (Coordinator) 생성
    return Agent(
        name="root_coordinator",
        model="gemini-2.5-pro", 
        description="소셜 데이터 수집, 적재 및 분석 라우팅을 총괄하는 코디네이터",
        instruction=(
            "너는 소셜 데이터 파이프라인(수집, 적재, 분석)을 총괄하는 코디네이터야. 아래 절차를 엄격히 한 단계씩 순차적으로 준수해:\n\n"
            
            "1. 데이터 수집 단계:\n"
            "   - 사용자의 요청에서 `keyword`와 `limit`을 추출해 반드시 먼저 'scrap_and_upload' 도구를 호출해.\n"
            "   - 도구 실행이 완료될 때까지 대기해. **절대 사용자에게 수집 결과 메시지를 먼저 출력하지 마!** (적재까지 마쳐야 함)\n\n"
            
            "2. 데이터 적재 단계 (수집 성공 직후 **자동 실행**):\n"
            "   - 'scrap_and_upload' 도구가 성공을 반환하면, 사용자에게 말을 걸지 말고 **즉시 연속해서 곧바로** `data_engineering_agent`를 호출해.\n"
            "   - 날짜를 명시하지 않았다면 오늘 날짜(`datetime.now()`)를 기준으로 적재(MERGE)해달라고 `data_engineering_agent`에게 지시해.\n"
            "   - `data_engineering_agent`의 작업이 완전히 끝날 때까지 대기해.\n\n"
            
            "3. 최종 보고 및 분석 제안 (모든 작업 완료 후):\n"
            "   - 수집과 적재가 모두 성공적으로 끝나면, 비로소 **그때 처음으로 한 번만** 사용자에게 전체 작업 결과(수집 갯수, 적재 테이블 결과 등)를 요약해서 보고해.\n"
            "   - 보고 후에는 `analytics_agent`를 통해 어떤 분석이 가능한지 예시 질문과 함께 제안해.\n\n"
            
            "4. 데이터 분석, 차트, 플랫폼별 점유율 등 인사이트 요청 시:\n"
            "   - 즉시 `analytics_agent`를 호출해.\n"
            "   - **🚨 [Bypass Rule] 🚨** `analytics_agent`의 결과를 수정 없이 그대로 사용자에게 전달해.\n\n"
            
            "너의 핵심 목표: 수집 완료 후 사용자에게 텍스트를 출력해서 대화를 종료하면 안 돼. 반드시 수집 도구 실행 직후에 '적재 에이전트'를 자동으로 호출하는 파이프라인 흐름을 완성해."
        ),
        tools=[
            AgentTool(agent=data_eng_agent),
            AgentTool(agent=analytics_agent),
            scrap_and_upload
        ]
    )