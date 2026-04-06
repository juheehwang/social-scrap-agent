import os
import uuid
from datetime import datetime
from google.cloud import storage
from dotenv import load_dotenv


class GCSUploader:
    def __init__(self, bucket_name: str):
        print("GCSUploader initialized")
        self.bucket_name = bucket_name or os.environ.get("GCS_BUCKET_NAME")
        # storage.Client()는 GOOGLE_APPLICATION_CREDENTIALS 또는 기본 인증 정보를 자동으로 찾습니다.
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)

    def upload_daily_report(self, local_file_path: str) -> str:
        """
        로컬 파일을 오늘 날짜(YYYY-MM-DD) 폴더 + UUID로 GCS에 업로드합니다.
        동시에 여러 사용자가 업로드해도 UUID로 인해 파일이 덮어씌워지지 않습니다.
        
        :param local_file_path: 로컬에 저장된 파일 경로 (예: reports/raw_social_data.json)
        :return: 업로드된 대상 파일명(Blob name)
        """
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"로컬 파일을 찾을 수 없습니다: {local_file_path}")
            
        today_str = datetime.now().strftime('%Y-%m-%d')
        unique_id = uuid.uuid4().hex[:8]  # 충돌 방지용 고유 ID
        destination_blob_name = f"reports/{today_str}/{unique_id}.json"
        
        blob = self.bucket.blob(destination_blob_name)
        blob.upload_from_filename(local_file_path)
        
        print(f"☁️ [GCS] 업로드 완료: gs://{self.bucket_name}/{destination_blob_name}")
        return destination_blob_name
