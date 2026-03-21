import os
from googleapiclient.discovery import build
from .models import SocialMediaPost

class YouTubeScraperAPI:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        if not self.api_key:
            raise ValueError("YouTube API Key가 필요합니다. 환경 변수 YOUTUBE_API_KEY를 설정하거나 직접 전달해주세요.")
        
        # YouTube Data API 서비스 객체 생성
        self.youtube = build("youtube", "v3", developerKey=self.api_key)

    def scrape(self, keyword: str, max_results: int = 5) -> list[dict]:
        """
        최신순으로 YouTube 동영상을 검색하고 조회수, 댓글 등을 수집합니다.
        
        Step 1: search.list (주어진 키워드로 최근 영상 검색)
        Step 2: videos.list (조회수, 채널명 등 상세 정보 일괄 조회)
        Step 3: commentThreads.list (각 영상별 댓글 조회)
        """
        print(f"📺 [YOUTUBE API] '{keyword}' 최신순 탐색...")
        
        results = []
        try:
            # Step 1: Search API를 사용하여 최신 영상 5개(여유있게 10개 조회 후 자체 필터링) 가져오기
            search_response = self.youtube.search().list(
                q=keyword,
                part="id,snippet",
                type="video",
                order="date", 
                maxResults=max_results * 2 # 노이즈(official 채널) 필터링을 위해 넉넉하게 가져옴
            ).execute()

            video_ids = []
            valid_items = []
            for item in search_response.get("items", []):
                channel_title = item["snippet"]["channelTitle"]
                # 기존 코드의 "official" 채널 필터링 로직 유지
                if "official" in channel_title.lower():
                    continue
                
                video_ids.append(item["id"]["videoId"])
                valid_items.append(item)
                
                if len(video_ids) >= max_results:
                    break
            
            if not video_ids:
                print("   ⚠️ 검색 결과가 없습니다.")
                return []

            # Step 2: Videos API를 사용하여 조회수(statistics)를 포함한 상세 정보 일괄(Batch) 조회
            videos_response = self.youtube.videos().list(
                part="snippet,statistics",
                id=",".join(video_ids)
            ).execute()

            for video_data in videos_response.get("items", []):
                video_id = video_data["id"]
                snippet = video_data["snippet"]
                statistics = video_data.get("statistics", {})

                title = snippet["title"]
                channel_title = snippet["channelTitle"]
                published_at = snippet.get("publishedAt") # 게시일자 추출
                url = f"https://www.youtube.com/watch?v={video_id}"
                
                # 조회수 파싱
                view_count = statistics.get("viewCount")
                views = int(view_count) if view_count is not None else None

                # Step 3: CommentThreads API를 사용하여 각 영상의 헤더 댓글 수집
                comments = []
                try:
                    comments_response = self.youtube.commentThreads().list(
                        part="snippet",
                        videoId=video_id,
                        order="relevance",
                        maxResults=15, # 기존 코드와 동일하게 최대 15개 수집
                        textFormat="plainText"
                    ).execute()

                    for comment_item in comments_response.get("items", []):
                        comment_text = comment_item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                        if comment_text.strip():
                            comments.append(comment_text.strip())
                except Exception as e:
                    # 댓글이 비활성화된 영상 등
                    print(f"   ⚠️ [YT API] {channel_title} 영상 댓글 수집 실패: {e}")

                # 통일된 모델(Entity) 생성
                post = SocialMediaPost(
                    platform="youtube",
                    title=title,
                    url=url,
                    owner=channel_title,
                    published_at=published_at,
                    views=views,
                    comments=comments
                )
                results.append(post.to_dict())
                print(f"   ✅ [YT API] 수집 완료: {channel_title} (조회수 {views or 0}회, 댓글 {len(comments)}개)")

        except Exception as e:
            print(f"❌ [YOUTUBE API] 오류 발생: {e}")
        
        return results
