import os

def load_instruction_from_md(file_name: str) -> str:
    """
    .gemini/agents/ 디렉터리에 있는 .md 파일을 읽어와 프롬프트(본문)만 추출합니다.
    """
    # 현재 파일(agents/md_loader.py) 위치를 기준으로 .md 파일의 절대 경로 계산
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    md_file_path = os.path.join(base_dir, ".gemini", "agents", file_name)
    
    if not os.path.exists(md_file_path):
        return f"에이전트 역할 및 지시사항을 정의해 주세요. ({file_name} 파일을 찾을 수 없습니다.)"

    with open(md_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # '---' 로 감싸진 메타데이터(YAML frontmatter) 제거
    parts = content.split("---")
    if len(parts) >= 3:
        # parts은 빈 문자열, parts[1]은 메타데이터, parts[2]가 본문
        instruction_text = "---".join(parts[2:]).strip()
        return instruction_text
    else:
        return content.strip()
