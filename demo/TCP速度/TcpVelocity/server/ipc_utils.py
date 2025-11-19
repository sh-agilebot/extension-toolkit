# -*- coding: utf-8 -*-
"""
IPC 工具方法。

TcpVelocity 采用“双进程”架构：FastAPI 主进程负责 HTTP/WebSocket 服务，
机器人子进程负责直连机器人并把状态写入 multiprocessing.Queue。
本模块提供若干基础设施，使主进程可以：

1. 以 spawn 方式启动机器人子进程（确保与 FastAPI 事件循环隔离）；
2. 将 Pydantic 模型或 dict 安全地放入/取出队列；
3. 启动消费者协程把队列数据交给 WebSocket 广播器；
4. 监视子进程存活状态并在异常退出后自动拉起。
"""

from __future__ import annotations

import asyncio
import multiprocessing as mp
import logging
from queue import Empty
from typing import Any, Awaitable, Callable


def start_process(
    target: Callable[..., Any], args: tuple = (), daemon: bool = True
) -> mp.Process:
    """
    启动一个子进程（spawn 上下文）。

    Args:
        target: 子进程入口函数。
        args: 传递给入口函数的参数。
        daemon: 是否以守护进程方式运行。
    """
    ctx = mp.get_context("spawn")
    p = ctx.Process(target=target, args=args, daemon=daemon)
    p.start()
    return p


async def async_queue_put(q: mp.Queue, item: Any) -> None:
    """
    在协程环境中向 multiprocessing.Queue 放入数据。

    Queue.put 是阻塞的，为避免卡住 FastAPI 事件循环，这里借助线程池执行。
    """
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, q.put, item)


def to_serializable(payload: Any) -> Any:
    """
    将 Pydantic 对象转换为 JSON 友好的类型，其余数据保持原样。

    子进程和主进程在不同解释器里，只有原生类型才能经由 IPC 传输。
    """
    try:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(exclude_none=True)
    except Exception:
        pass
    return payload


async def queue_consumer_loop(
    q: mp.Queue,
    handler: Callable[[Any], Awaitable[None]],
    poll_interval: float = 0.01,
) -> None:
    """
    不断从队列消费数据并交给 handler。

    FastAPI lifespan 在启动 IPCManager 时会创建该任务，职责是把子进程发来的
    数据交给广播层。为防止阻塞，这里采用“短轮询 + await handler”方式。
    """
    while True:
        try:
            item = q.get_nowait()
        except Empty:
            await asyncio.sleep(poll_interval)
            continue

        try:
            await handler(item)
        except Exception:  # noqa: BLE001
            # handler 内部会记录异常，这里只保证循环不中断
            pass


async def watch_and_restart(
    get_proc: Callable[[], mp.Process | None],
    set_proc: Callable[[mp.Process], None],
    restart_factory: Callable[[], mp.Process],
    interval: float = 2.0,
    log: logging.Logger | None = None,
) -> None:
    """
    监控指定子进程状态并在意外退出后重启。

    Args:
        get_proc: 获取当前被监控进程的函数
        set_proc: 设置/替换当前进程引用的函数
        restart_factory: 无参工厂函数，负责启动并返回新的进程
        interval: 轮询间隔（秒）
        log: 可选日志器
    """

    while True:
        try:
            p = get_proc()
        except Exception:
            p = None

        need_restart = (p is None) or (not p.is_alive())
        if need_restart:
            try:
                if log:
                    log.warning("检测到子进程已退出，正在尝试重新拉起")
                new_p = restart_factory()
                set_proc(new_p)
            except Exception:
                if log:
                    log.exception("重启子进程失败")
        await asyncio.sleep(interval)


class IPCManager:
    """
    封装“启动子进程 + 队列消费者 + watcher”这一整套流程。

    FastAPI lifespan 调用 `await IPCManager.start()` 后会得到：
    - 子进程：调用 spawn_proc(queue) 启动；
    - 消费任务：queue_consumer_loop -> handler -> WebSocket 广播；
    - 监视任务：watch_and_restart 防止子进程意外退出。
    关闭 FastAPI 时再调用 stop，保证所有后台任务/进程都被收敛。
    """

    def __init__(
        self,
        spawn_proc: Callable[[mp.Queue], mp.Process],
        handler: Callable[[Any], Awaitable[None]],
        log: logging.Logger | None = None,
        watch_interval: float = 2.0,
        poll_interval: float = 0.01,
    ) -> None:
        self._spawn_proc = spawn_proc
        self._handler = handler
        self._log = log
        self._watch_interval = watch_interval
        self._poll_interval = poll_interval

        self._queue: mp.Queue | None = None
        self._proc: mp.Process | None = None
        self._consumer_task: asyncio.Task | None = None
        self._watcher_task: asyncio.Task | None = None

    def _get_proc(self) -> mp.Process | None:
        return self._proc

    def _set_proc(self, p: mp.Process) -> None:
        self._proc = p

    def _restart(self) -> mp.Process:
        # 复用已有的 Queue，使新子进程继续向同一通道写数据
        return self._spawn_proc(self._queue)  # type: ignore[arg-type]

    async def start(self) -> None:
        """
        启动 IPC 所需的全部组件：
        1. 创建 multiprocessing.Queue；
        2. 启动子进程；
        3. 拉起队列消费者任务；
        4. 拉起 watcher 任务。
        """
        ctx = mp.get_context("spawn")
        self._queue = ctx.Queue()
        self._proc = self._spawn_proc(self._queue)

        self._consumer_task = asyncio.create_task(
            queue_consumer_loop(
                self._queue, self._handler, poll_interval=self._poll_interval
            )
        )
        self._watcher_task = asyncio.create_task(
            watch_and_restart(
                self._get_proc,
                self._set_proc,
                self._restart,
                interval=self._watch_interval,
                log=self._log,
            )
        )
        if self._log:
            self._log.info("IPC 管理器已启动")

    async def stop(self) -> None:
        """
        停止 watcher/consumer 任务并终止子进程。

        FastAPI lifespan 的 shutdown 阶段会调用此方法，确保不留下僵尸进程。
        """
        for task in (self._watcher_task, self._consumer_task):
            if task:
                task.cancel()
        try:
            await asyncio.gather(
                *(t for t in (self._watcher_task, self._consumer_task) if t),
                return_exceptions=True,
            )
        except Exception:
            pass

        # 终止子进程
        p = self._proc
        if p and isinstance(p, mp.Process):
            try:
                if p.is_alive():
                    p.terminate()
                    p.join(timeout=2)
            except Exception:
                pass
        if self._log:
            self._log.info("IPC 管理器已停止")
