from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class VideoRequest(BaseModel):
    url: str

@app.get("/")
def read_root():
    return {"status": "Studio 100 Ton Engine Running", "power": "100%"}

@app.post("/ignite")
def ignite_engine(request: VideoRequest):
    # 여기에 나중에 실제 크롤링 및 영상 생성 로직이 연결됩니다.
    # 지금은 연결 테스트용 응답만 보냅니다.
    print(f"Received Order for: {request.url}")
    return {
        "status": "processing",
        "message": "100톤 엔진이 가동되었습니다.",
        "target_url": request.url
    }
