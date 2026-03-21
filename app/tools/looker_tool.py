def get_looker_dashboard_url(keyword: str = None) -> str:
    """
    분석 데이터에 대한 시각화 대시보드(Looker Studio) 접속 URL을 반환합니다.
    사전에 구축된 Looker Studio 보고서 링크를 제공하며, 필요시 키워드를 파라미터로 넘길 수 있습니다.
    
    Args:
        keyword (str, optional): 보고서에서 기본 필터로 사용할 검색어 (예: "봄신상")
        
    Returns:
        str: 시각화 대시보드 URL 안내 메시지
    """
    
    # [TO-DO] 이 URL은 실제 사용자님이 생성하신 Looker Studio 리포트 공유 링크로 교체해야 합니다.
    # 예시: https://lookerstudio.google.com/reporting/your-report-id/page/your-page-id
    base_url = "https://lookerstudio.google.com/navigation/reporting" 
    
    msg = f"📈 **[데이터 시각화]**\n자세한 데이터 시각화 차트는 다음 Looker 대시보드에서 실시간으로 확인하실 수 있습니다:\n👉 {base_url}"
    
    if keyword:
        # Looker Studio URL 필터 파라미터 구조에 맞춰 변환 가능
        msg += f"\n*(현재 분석 키워드: '{keyword}' - 대시보드 내 필터에 적용해 보세요)*"
        
    return msg
