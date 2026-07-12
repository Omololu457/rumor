import asyncio
import io
import os
import uuid

import qrcode
from fastapi import FastAPI, Form, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.game_state import game
from app.net import get_local_ip

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")

app = FastAPI(title="Rumor")
db.init_db()

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# ---------- Connection registry for the WebSocket ----------

class ConnectionManager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, pid: str, ws: WebSocket):
        await ws.accept()
        self.active[pid] = ws

    def disconnect(self, pid: str):
        self.active.pop(pid, None)
        if pid in game.state["players"]:
            game.state["players"][pid]["connected"] = False

    async def send_to(self, pid: str):
        ws = self.active.get(pid)
        if ws is None:
            return
        try:
            await ws.send_json(game.public_view_for(pid))
        except Exception:
            self.disconnect(pid)

    async def broadcast(self):
        for pid in list(self.active.keys()):
            await self.send_to(pid)


manager = ConnectionManager()


# ---------- Background clock: drives phase timers for everyone ----------

@app.on_event("startup")
async def start_clock():
    async def loop():
        while True:
            before = game.state["phase"]
            game.tick()
            if game.state["phase"] != before or before in ("action", "vote"):
                await manager.broadcast()
            await asyncio.sleep(1)

    asyncio.create_task(loop())


# ---------- Pages ----------

@app.get("/", response_class=HTMLResponse)
async def join_page(request: Request):
    pid = request.cookies.get("player_id")
    if pid and pid in game.state["players"]:
        return RedirectResponse("/game")
    return templates.TemplateResponse("join.html", {"request": request})


@app.post("/join")
async def join(request: Request, name: str = Form(...), descriptor: str = Form(""),
                photo: UploadFile | None = None):
    photo_filename = None
    if photo is not None and photo.filename:
        ext = os.path.splitext(photo.filename)[1].lower() or ".jpg"
        photo_filename = f"{uuid.uuid4().hex}{ext}"
        contents = await photo.read()
        with open(os.path.join(UPLOAD_DIR, photo_filename), "wb") as f:
            f.write(contents)

    pid, error = game.add_player(name, descriptor, photo_filename)
    if error:
        return templates.TemplateResponse("join.html", {"request": request, "error": error})

    resp = RedirectResponse("/game", status_code=303)
    resp.set_cookie("player_id", pid, max_age=60 * 60 * 12)
    return resp


@app.get("/game", response_class=HTMLResponse)
async def game_page(request: Request):
    pid = request.cookies.get("player_id")
    if not pid or pid not in game.state["players"]:
        return RedirectResponse("/")
    return templates.TemplateResponse("game.html", {"request": request, "player_id": pid})


@app.get("/display", response_class=HTMLResponse)
async def display_page(request: Request):
    """Meant for a laptop/TV screen, not a phone -- shows the QR + address
    so everyone else can join."""
    ip = get_local_ip()
    return templates.TemplateResponse(
        "display.html",
        {"request": request, "ip": ip, "port": 8000, "url": f"http://{ip}:8000"},
    )


@app.get("/qr.png")
async def qr_code():
    ip = get_local_ip()
    url = f"http://{ip}:8000"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


# ---------- WebSocket: real-time state sync ----------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    cookies = ws.cookies
    pid = cookies.get("player_id")
    if not pid or pid not in game.state["players"]:
        await ws.close(code=4001)
        return

    await manager.connect(pid, ws)
    game.state["players"][pid]["connected"] = True
    await manager.broadcast()

    try:
        while True:
            msg = await ws.receive_json()
            msg_type = msg.get("type")

            if msg_type == "action":
                game.submit_action(pid, msg.get("action"), msg.get("rumor_id"))
            elif msg_type == "vote":
                game.submit_vote(pid, msg.get("ballot", {}))
            elif msg_type == "host_start":
                game.start_game(pid)
            elif msg_type == "host_end_round":
                game.host_end_round_early(pid)
            elif msg_type == "host_end_game":
                game.host_end_game(pid)
            elif msg_type == "host_reset":
                game.reset_lobby(pid)

            await manager.broadcast()
    except WebSocketDisconnect:
        manager.disconnect(pid)
        await manager.broadcast()
