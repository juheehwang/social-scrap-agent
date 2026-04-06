from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class SocialMediaPost:
    """소셜 미디어 크롤링 결과를 담는 통합 엔티티"""
    platform: str        # 플랫폼 이름 (youtube 등)
    title: str           # 게시물 제목 (또는 본문/캡션 내용 일부)
    url: str             # 게시물 링크
    owner: str           # 소유자 (유튜버 채널명 등)
    views: Optional[int] # 조회수 (조회수 숨김 처리 등으로 수집 불가능할 때를 대비해 Optional 적용)
    published_at: Optional[str] = None # 게시일자 (ISO 8601 포맷 등)
    comments: List[str] = field(default_factory=list) # 댓글 리스트
    content: Optional[str] = None # 영상 내용 분석
    
    def to_dict(self):
        """저장 및 분석을 위해 JSON/Dict 형태로 반환"""
        return {
            "platform": self.platform,
            "title": self.title,
            "url": self.url,
            "owner": self.owner,
            "published_at": self.published_at,
            "views": self.views,
            "comments": self.comments,
            "comment_count": len(self.comments),
            "content": self.content
        }
