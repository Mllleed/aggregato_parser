import asyncio

from threading import Event
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from main2 import main, progress
import os

stop_event = Event()
parser_running = False

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


async def run_parser(data):
    global parser_running
    parser_running = True
    print("✅ Парсер запущен:", data)

    excel_path = await asyncio.to_thread(
        main, data.get('category'), data.get('region'), data.get('dataSource'), data.get('check_data')
    )

    parser_running = False
    print("🛑 Парсер остановлен")

    if excel_path and os.path.exists(excel_path):
        print(f"📂 Файл готов: {excel_path}")
        return excel_path
    else:
        print("❌ Файл не найден")
        return None


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/start")
async def start_parser(request: Request):
    global parser_running
    if parser_running:
        return {"status": "already_running"}

    data = await request.json()
    stop_event.clear()

    progress["status"] = "running"
    progress["processed"] = 0
    progress["percent"] = 0
    progress["total"] = None
    progress["message"] = "Начинаю..."

    excel_path = await run_parser(data)

    if excel_path:
        progress["status"] = "done"
        progress["message"] = "Готово"
        filename = os.path.basename(excel_path)
        return {"status": "completed", "download_url": f"/download/{filename}"}

    progress["status"] = "error"
    return {"status": "error", "message": "Не удалось создать файл"}


@app.get('/progress')
async def get_progress():
    return progress


@app.post("/stop")
def stop_parser():
    progress["status"] = "stopped"
    progress["message"] = "Остановлено пользователем"
    return {"status": "stopped"}


@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(os.getcwd(), filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=filename)
    return {"error": "Файл не найден"}
