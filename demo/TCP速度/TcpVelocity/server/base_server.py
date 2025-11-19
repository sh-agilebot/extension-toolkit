import json
import asyncio
import logging
from fastapi import WebSocket
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BaseWebSocketServer:
    """
    WebSocket 广播管理器。

    FastAPI 的 `/ws` 端点依赖该类统一维护在线客户端，并把来自机器人子进程的
    事件广播给前端，实现“机器人 → IPC → WebSocket → UI”的推送链路。

    能力：
    - register/unregister：与 websocket_endpoint 配合维护连接集合；
    - broadcast：接受 dict 或 Pydantic 模型并序列化为 JSON 文本广播；
    - 自动断连处理：发送失败时清理失效连接，保持集合健康。
    """

    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._clients_lock = asyncio.Lock()

    async def broadcast(self, body: dict | BaseModel):
        """
        把消息广播给所有客户端。

        Args:
            body: 可以是 dict 或 Pydantic 模型；会被统一序列化为 JSON 文本。
        """
        # Pydantic v2 模型可直接 model_dump，普通 dict 则原样转换
        message = (
            json.dumps(body.model_dump(exclude_none=True), ensure_ascii=False)
            if isinstance(body, BaseModel)
            else json.dumps(body, ensure_ascii=False)
        )

        async with self._clients_lock:
            clients = list(self._clients)
        if not clients:
            return

        # 收集发送失败的客户端，批量剔除，避免在锁内做大量 IO
        to_remove = []
        for ws in clients:
            try:
                await ws.send_text(message)
            except Exception:
                to_remove.append(ws)

        if to_remove:
            async with self._clients_lock:
                for ws in to_remove:
                    self._clients.discard(ws)
            logger.warning(f"已自动清理 {len(to_remove)} 个失效的 WebSocket 连接")

    async def register_client(self, websocket: WebSocket):
        """新客户端接入时调用，加入集合以便后续广播。"""
        async with self._clients_lock:
            self._clients.add(websocket)
        logger.info(f"客户端已连接，当前在线数量：{len(self._clients)}")

    async def unregister_client(self, websocket: WebSocket):
        """客户端断开时调用，避免悬挂引用导致内存泄露。"""
        async with self._clients_lock:
            self._clients.discard(websocket)
        logger.info(f"客户端已断开，当前在线数量：{len(self._clients)}")
