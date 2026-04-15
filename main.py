from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from supabase import create_client, Client

app = FastAPI()

# 1. 수파베이스 설정 (본인의 정보로 꼭 수정하세요!)
url = "https://dwqngzohkbyexatcushx.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImR3cW5nem9oa2J5ZXhhdGN1c2h4Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQyMzM2NjYsImV4cCI6MjA4OTgwOTY2Nn0.EeqB08aL0wmG8vMqDCYA3vltQ1jWuMC_RcyQcoetAb4"
supabase: Client = create_client(url, key)

# --- 공통 테이블 생성 함수 ---
def generate_table_html(data, title, color="#FF6B6B"):
    if not data:
        return f"<html><body><h2>'{title}' 데이터가 없습니다. RLS를 확인하세요!</h2><a href='/'>홈으로</a></body></html>"
    
    columns = data[0].keys()
    header = "".join([f"<th>{col}</th>" for col in columns])
    rows = "".join(["<tr>" + "".join([f"<td>{item.get(col, '')}</td>" for col in columns]) + "</tr>" for item in data])
    
    return f"""
    <html>
        <head>
            <style>
                body {{ font-family: sans-serif; padding: 30px; background: #fefefe; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }}
                th, td {{ border: 1px solid #eee; padding: 15px; text-align: left; }}
                th {{ background-color: {color}; color: white; }}
                .back {{ display: inline-block; margin-bottom: 20px; text-decoration: none; color: {color}; font-weight: bold; }}
            </style>
        </head>
        <body>
            <a href="/" class="back">⬅️ "그래서 이제 뭐함?" 본부로</a>
            <h1>🔍 {title} 실시간 데이터</h1>
            <table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>
        </body>
    </html>
    """

# --- [메인 홈 화면] ---
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head>
            <title>그래서 이제 뭐함? - Admin</title>
            <style>
                body { font-family: sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; background: #fff; margin: 0; }
                .card { text-align: center; border: 3px solid #FF6B6B; padding: 50px; border-radius: 30px; width: 450px; }
                .title { color: #FF6B6B; font-size: 3.5rem; font-weight: 900; margin-bottom: 5px; }
                .sub { color: #333; font-size: 1.2rem; margin-bottom: 40px; font-weight: bold; }
                .btn-group { display: flex; flex-direction: column; gap: 15px; }
                .btn { display: block; padding: 18px; color: white; text-decoration: none; border-radius: 15px; font-weight: bold; font-size: 1.1rem; transition: 0.2s; }
                .btn-tasks { background: #FF6B6B; }
                .btn-recurring { background: #4D96FF; }
                .btn:hover { opacity: 0.8; transform: scale(1.02); }
            </style>
        </head>
        <body>
            <div class="card">
                <div class="title">그래서 이제 뭐함?</div>
                <div class="sub">공강 시간 자동 스케줄링 시스템</div>
                <div class="btn-group">
                    <a href="/view-tasks" class="btn btn-tasks">📋 할 일(Tasks) 목록 보기</a>
                    <a href="/view-recurring" class="btn btn-recurring">🔄 반복 일정(Recurring) 보기</a>
                </div>
            </div>
        </body>
    </html>
    """

@app.get("/view-tasks", response_class=HTMLResponse)
def view_tasks():
    res = supabase.table("tasks").select("*").execute()
    return HTMLResponse(content=generate_table_html(res.data, "할 일 (Tasks)", "#FF6B6B"))

@app.get("/view-recurring", response_class=HTMLResponse)
def view_recurring():
    res = supabase.table("recurring_schedule").select("*").execute()
    return HTMLResponse(content=generate_table_html(res.data, "반복 일정 (Recurring)", "#4D96FF"))