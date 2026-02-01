from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import requests
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from openai import OpenAI
import uuid

# 1. 환경변수 로드
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

app = FastAPI()

# 오디오 저장소 설정
if not os.path.exists("static"):
    os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS 설정 (모든 접속 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    url: str

# --- [기능 1] 슈퍼 크롤러 (네이버/쿠팡 방어막 뚫기) ---
def crawl_site(url: str):
    # 봇 차단 회피를 위한 '가짜 신분증' (User-Agent)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # 🔥 핵심: 한글 깨짐 방지 (네이버는 EUC-KR을 씀)
        response.encoding = response.apparent_encoding 
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 제목 가져오기
        title = ""
        if soup.title:
            title = soup.title.string
        else:
            meta_title = soup.find("meta", property="og:title")
            title = meta_title["content"] if meta_title else "제목 없음"
        
        # 본문 가져오기 (메타 태그 -> id="dic_area"(네이버뉴스) -> p태그 순서로 시도)
        content = ""
        meta_desc = soup.find("meta", property="og:description")
        if meta_desc:
            content = meta_desc["content"]
        
        # 네이버 뉴스 본문 전용 처리
        if not content or len(content) < 20:
            naver_content = soup.select_one("#dic_area")
            if naver_content:
                content = naver_content.get_text().strip()
            else:
                content = soup.get_text()[:500].strip()

        # 이미지 가져오기
        images = []
        # 메타 이미지(대표 썸네일) 1순위
        meta_img = soup.find("meta", property="og:image")
        if meta_img:
            images.append(meta_img["content"])
            
        for img in soup.find_all('img'):
            src = img.get('src')
            if src and src.startswith('http'):
                # 너무 작은 아이콘 제외
                if "icon" not in src and "logo" not in src:
                    images.append(src)
        
        # 중복 제거 후 5개만
        images = list(dict.fromkeys(images))[:5]
        
        return {"title": title, "content": content[:1000], "images": images, "status": "success"}
    except Exception as e:
        print(f"❌ 크롤링 에러: {str(e)}")
        return {"status": "error", "message": str(e)}

# --- [기능 2] 대본 작가 ---
def generate_script(title, content):
    print("🤖 GPT 작성 시작...")
    try:
        prompt = f"""
        너는 유튜브 쇼츠 전문 대본 작가야.
        제목: {title}
        내용: {content}
        
        위 내용을 바탕으로 30초 길이의 흥미진진한 대본을 써줘.
        첫 문장은 무조건 호기심을 자극해야 해.
        말투는 "~대박이죠?", "~놀라지 마세요" 같은 친근한 구어체로 써.
        오직 대본 텍스트만 출력해.
        """
        response = client.chat.completions.create(
            model="gpt-4o", 
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices.message.content
    except Exception as e:
        print(f"❌ 대본 에러: {e}")
        return "죄송합니다. 대본 작성 중 오류가 발생했습니다."

# --- [기능 3] AI 성우 ---
def generate_audio(script):
    print("🎙️ 녹음 시작...")
    try:
        response = client.audio.speech.create(
            model="tts-1",
            voice="onyx",
            input=script
        )
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join("static", filename)
        with open(filepath, "wb") as f:
            f.write(response.content)
        return filename
    except Exception as e:
        print(f"❌ 녹음 에러: {e}")
        return None

@app.post("/ignite")
def ignite_engine(request: VideoRequest):
    print(f"🔥 요청 수신: {request.url}")
    
    data = crawl_site(request.url)
    if data["status"] == "error":
        return {"message": "정보 수집 실패", "error": data["message"]}
    
    script = generate_script(data['title'], data['content'])
    audio_file = generate_audio(script)
    
    # ⚠️ 중요: 사장님 서버 IP 확인 (Source 165, 170 참고: 3.27.133.204)
    audio_url = f"http://3.27.133.204:8000/static/{audio_file}" if audio_file else None

    return {
        "status": "success",
        "crawled_title": data['title'],
        "script": script,
        "images": data['images'],
        "audio_url": audio_url
    }
