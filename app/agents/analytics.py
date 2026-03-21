import os
from google.adk.agents import Agent
from app.tools.bq_analyzer import execute_bq_query
from app.tools.looker_tool import get_looker_dashboard_url

def get_analytics_agent(bq_mcp_tools: list = None) -> Agent:
    # 환경변수에서 BQ 테이블 정보 가져오기 (없으면 대비할 기본값)
    dataset_id = os.environ.get("BQ_DATASET_ID", "social_dataset")
    table_name = os.environ.get("BQ_TABLE_NAME", "daily_social_scrap")
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT") or "my-youtube-scraper-489216"
    
    target_table = f"`{project_id}.{dataset_id}.{table_name}`"

    return Agent(
        name="analytics_agent",
        model="gemini-2.5-pro",
        description="BigQuery에서 소셜 데이터를 조회하고, 사용자와 대화하며 결과를 분석 및 시각화 URL을 제공하는 에이전트",
        instruction=(
            "너는 소셜 데이터 전문 데이터 분석가야. 사용자가 분석이나 확인을 요청하면 아래 단계를 엄격히 따라:\n\n"
            "1. **SQL 조회**: 사용자의 질문 의도를 파악하고 'execute_bq_query' 도구에 정확한 BigQuery 표준 SQL 구문을 작성하여 쿼리를 실행해.\n"
            f"   - 타겟 테이블은 반드시 {target_table} 를 사용해야 해.\n"
            "   - 데이터 검색 시에는 Like나 REGEXP를 사용하여 키워드를 유연하게 찾아.\n\n"
            "2. **친절한 요약**: 쿼리 결과를 바탕으로 인사이트(예: 가장 많이 언급된 플랫폼, 좋아요가 많은 게시글 특징 등)를 자연어로 친절하게 요약해.\n\n"
            "3. **시각화 제공**: 요약 뒤에 'get_looker_dashboard_url' 도구를 호출하여 Looker Studio 대시보드 접근용 안내 메시지를 덧붙여 줘.\n\n"
            "4. **[필수] 후속 질문 제안**: 답변의 가장 마지막에 사용자가 이어서 분석해 볼 만한 흥미로운 '추가 질문 추천(Follow-up Questions)' 3가지를 명확히 제시해.\n"
            "   - 예: '이 데이터와 관련해 다음 세 가지를 더 분석해 보시겠어요?'\n"
            "5. **[필수] 출력 내용 및 형식**: 네가 `execute_bq_query`로 받은 데이터를 **단 하나도 빠짐없이** 사용자에게 보여줘야 해. 단순히 '조회 완료'라고 하지 말고, **Markdown 표(Table)**나 **구조화된 리스트** 형식으로 조회된 실제 수치를 화면에 뿌려줘.\n\n"
            "너의 목표는 사용자가 BigQuery UI에 들어가지 않고도 터미널(또는 채팅창)에서 깊이 있는 데이터 탐색을 계속 이어가도록 만드는 거야. **절대 대화를 먼저 종료하지 말고, 항상 데이터 표와 후속 질문을 제안하며 답변을 마무리해.**"
        ),
        tools=[execute_bq_query, get_looker_dashboard_url],  
        disallow_transfer_to_peers=True
    )