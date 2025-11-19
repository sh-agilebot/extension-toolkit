# -*- coding: utf-8 -*-
"""
主服务入口文件

功能包含：
- FastAPI HTTP 后端；
- WebSocket 实时推送；
- IPC（进程间通信）管理，与机器人子进程交互；
- 前端页面渲染（Jinja2 + 静态资源托管）。

整体流程：
1. FastAPI 启动时，通过 lifespan：
   - 启动机器人子进程；
   - 启动 IPC 管理器并监听机器人事件；
   - 将机器人事件广播给 WebSocket 客户端。
2. HTTP 与 WebSocket 服务对外提供接口。
3. FastAPI 关闭时自动停止 IPC 管理器与子进程。
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from server.base_server import BaseWebSocketServer
from server.robot_worker import start_robot_process
from server.ipc_utils import IPCManager
from server.config import ASSETS_DIR, ROOT_DIR, ROBOT_IP, PORT, HOST
from server.logger import logger
from server.state import SharedState
from server.models import MessageType, SetTcpVelocityIndexRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理：
    - startup：启动机器人子进程与 IPC 管理器；
    - shutdown：停止 IPC 管理器（内部完成任务取消与进程终止）。
    """

    async def _ipc_handle(item):
        """队列消息处理：广播到 WebSocket，并维护 TCP 速度缓存。"""
        try:
            await ws_server.broadcast(item)
        except Exception:
            logger.exception("广播消息失败")
        if isinstance(item, dict) and item.get("type") == MessageType.TCP_VELOCITY:
            try:
                SharedState.set("last_tcp_velocity", float(item.get("velocity") or 0.0))
            except Exception:
                pass

    spawn = lambda q: start_robot_process(ROBOT_IP, q)
    ipc = IPCManager(
        spawn_proc=spawn, handler=_ipc_handle, log=logger, watch_interval=2.0
    )
    await ipc.start()
    logger.info("机器人服务已启动")

    try:
        yield
    finally:
        logger.info("关闭中...")
        try:
            await ipc.stop()
        except Exception:
            pass


# ==========================
# FastAPI 应用
# ==========================
app = FastAPI(lifespan=lifespan)
# WebSocket 广播器
ws_server = BaseWebSocketServer()

# === 挂载静态文件 ===
if os.path.isdir(ASSETS_DIR):
    app.mount(
        "/assets",
        StaticFiles(directory=ASSETS_DIR, follow_symlink=True),
    )
    templates = Jinja2Templates(directory=ROOT_DIR)


@app.get("/")
def index(request: Request):
    """前端页面"""
    return templates.TemplateResponse(request=request, name="index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 实时推送接口"""
    await websocket.accept()
    await ws_server.register_client(websocket)

    try:
        # 保持连接，等待客户端心跳
        while True:
            await websocket.receive_text()
    except Exception:
        logger.warning("客户端断开连接")
    finally:
        await ws_server.unregister_client(websocket)


@app.post("/api/set_tcp_velocity_r_index")
async def set_tcp_velocity_r_index(body: SetTcpVelocityIndexRequest):
    """
    设置 TCP 速度写入R寄存器的索引
    此接口供简单服务调用
    POST /api/set_tcp_velocity_r_index
    Body: {"index": 5}
    """
    r_index = body.index
    SharedState.set("tcp_velocity_r_index", r_index)
    logger.info(f"设置 TCP 速度写入R寄存器的索引为: {r_index}")

    return {"result": True}


# ==========================
# 程序入口
# ==========================
if __name__ == "__main__":
    uvicorn.run(
        app, host=HOST, port=PORT, log_level="info", timeout_graceful_shutdown=0
    )
