# -*- coding: utf-8 -*-
"""
机器人子进程入口。

FastAPI 主进程不会直接与机器人通讯，而是通过 multiprocessing 启动本文件中的
robot_main：该子进程负责运行事件循环、连接机器人、监听状态并把加工后的数据
写入 IPC 队列，供主进程进一步广播给 WebSocket 客户端。
"""


def robot_main(robot_ip: str, retry_interval: int, out_queue):
    """
    子进程主函数：创建 RobotService 并把消息写入 IPC 队列。

    Args:
        robot_ip: 目标机器人 IP。
        retry_interval: RobotService 连接失败后的重试间隔。
        out_queue: multiprocessing.Queue，用于向主进程发送消息。
    """
    import asyncio

    from server.robot_services import RobotService as _RobotService
    from server.ipc_utils import async_queue_put, to_serializable
    from server.logger import logger

    async def _queue_broadcast(body):
        """
        RobotService 在子进程中调用的“广播函数”。

        本质是把 Pydantic/字典转换为可序列化数据后写入 IPC 队列。
        """
        data = to_serializable(body)
        await async_queue_put(out_queue, data)

    async def _run():
        """运行机器人通讯逻辑；异常时记录日志后退出进程。"""
        service = _RobotService(
            robot_ip=robot_ip,
            broadcaster=_queue_broadcast,
            retry_interval=retry_interval,
        )
        try:
            await service.connect_robot()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            logger.error(f"robot worker 异常退出: {e}")

    asyncio.run(_run())


def start_robot_process(robot_ip: str, q):
    """
    启动机器人子进程。

    FastAPI lifespan 会调用本方法获取 Process 对象，并交由 IPCManager 管理。
    """
    from server.ipc_utils import start_process

    # 默认将重试间隔设为 5 秒；如需自定义可以在主进程调用处调整
    return start_process(robot_main, (robot_ip, 5, q), daemon=True)
