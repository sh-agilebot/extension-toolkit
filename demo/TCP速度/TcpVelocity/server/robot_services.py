import math
import time
import logging
from typing import Optional

from Agilebot import Arm, StatusCodeEnum, RobotTopicType
from server.models import (
    Position,
    TcpVelocityMessage,
    RunningProgramMessage,
)
from server.state import SharedState

logger = logging.getLogger(__name__)


class RobotService:
    """
    机器人通讯 + 数据加工 + WebSocket 广播的桥梁。

    运行流程：
    1. 通过 Agilebot Python SDK 与机器人保持长连接，订阅笛卡尔位置与 TP 程序状态；
    2. 在 handle_cartesian_position 中基于相邻位置计算 TCP 速度；
    3. 每秒把实时速度同步到配置指定的 R 寄存器；
    4. 将速度/程序名称通过 broadcaster 函数写入 IPC 队列，最终推送到前端。
    """

    def __init__(self, robot_ip: str, broadcaster, retry_interval: int = 5):
        """
        Args:
            robot_ip: 机器人 IP。
            broadcaster: 一个协程函数，用于把处理好的消息发回主进程（通过 IPC）。
            retry_interval: 连接失败后的重试间隔，单位秒。
        """
        self.robot_ip = robot_ip
        self.retry_interval = retry_interval
        self.arm: Optional[Arm] = None
        self.broadcast = broadcaster

        self._last_pose: Optional[tuple[float, float, float]] = None
        """上一次的坐标"""
        self._last_time: Optional[float] = None
        """上一次的时间"""
        self._last_tcp_velocity: float = 0.0
        """上一次的速度"""
        self._last_sync_tcp_velocity_time: float = time.perf_counter()
        """上一次同步速度到R寄存器的时间"""

    # --------------------------
    # 机器人数据解析 & 推送
    # --------------------------
    @staticmethod
    def _extract_xyz(message) -> Optional[tuple[float, float, float]]:
        """
        从机器人消息结构中提取 (x, y, z)。

        消息示例：
        {
            "values": {
                "data2": {
                    "pose": {
                        "data": [x, y, z, ...]
                    }
                }
            }
        }
        """
        try:
            pose_data = (
                message.get("values", {}).get("data2", {}).get("pose", {}).get("data")
            )
            if not isinstance(pose_data, (list, tuple)) or len(pose_data) < 3:
                return None
            return float(pose_data[0]), float(pose_data[1]), float(pose_data[2])
        except Exception:
            return None

    def get_last_tcp_velocity(self) -> float:
        """供其他模块查询最近一次的 TCP 速度值。"""
        return self._last_tcp_velocity

    async def handle_cartesian_position(self, message: dict):
        """
        计算 TCP 末端速度，并通过 IPC 广播到主进程。

        处理步骤：
        1. 解析 XYZ 坐标；
        2. 与上一帧坐标比较，求得欧式距离；
        3. 用距离/时间差得到速度（mm/s）；
        4. 每秒将速度写入配置的 R 寄存器；
        5. 组织 TcpVelocityMessage，交由 broadcaster 发送给 WebSocket。
        """
        xyz = self._extract_xyz(message)
        if xyz is None:
            return

        now = time.perf_counter()

        # 若为第一次接收或刚启动，初始化上次坐标与时间，不计算速度
        if self._last_pose is None or self._last_time is None:
            self._last_pose, self._last_time = xyz, now
            return

        # 计算两次采样的时间间隔（秒）
        dt = now - self._last_time
        if dt <= 0:
            return

        # 计算三维空间位移
        dx, dy, dz = (
            xyz[0] - self._last_pose[0],
            xyz[1] - self._last_pose[1],
            xyz[2] - self._last_pose[2],
        )
        # 欧几里得距离（即 TCP 末端实际移动距离，单位：mm）
        distance = math.sqrt(dx**2 + dy**2 + dz**2)

        # 线速度 = 距离 / 时间间隔（mm/s）
        velocity = distance / dt

        # 更新缓存
        self._last_pose, self._last_time, self._last_tcp_velocity = xyz, now, velocity

        r_index = SharedState.get("tcp_velocity_r_index")
        if r_index is not None and r_index > 0:
            # 每秒同步一次到R，防止控制器压力过大
            dt = time.perf_counter() - self._last_sync_tcp_velocity_time
            if dt >= 1:
                ret = self.arm.register.write_R(r_index, self._last_tcp_velocity)
                if ret != StatusCodeEnum.OK:
                    logger.error(f"写入 R 寄存器失败，返回值: {ret.errmsg}")
                self._last_sync_tcp_velocity_time = time.perf_counter()

        await self.broadcast(
            TcpVelocityMessage(
                velocity=round(self._last_tcp_velocity, 3),
                position=Position(
                    x=round(xyz[0], 3),
                    y=round(xyz[1], 3),
                    z=round(xyz[2], 3),
                ),
            )
        )

    async def handle_tp_program_status(self, message: dict):
        """读取 TP 解释器状态并广播当前运行的程序名称。"""
        try:
            program_name = message["values"]["interpreter_status"][0]["program_name"]
        except KeyError:
            program_name = ""
        await self.broadcast(RunningProgramMessage(program_name=program_name))

    async def handle_robot_message(self, message: dict):
        """
        根据订阅的 topic 路径分发不同的处理逻辑。
        """
        try:
            path = message.get("path")
            if path == RobotTopicType.CARTESIAN_POSITION:
                await self.handle_cartesian_position(message)
            elif path == RobotTopicType.TP_PROGRAM_STATUS:
                await self.handle_tp_program_status(message)
            else:
                logger.warning(f"收到未处理的 Topic: {path}")
        except Exception as e:
            logger.error(f"下行消息分发异常: {str(e)}")

    async def connect_robot(self):
        """
        与机器人建立连接并订阅所需 Topic。

        该方法在机器人子进程中运行：一旦连接成功，就会启动 sub_pub，
        将后续收到的状态消息交给 handle_robot_message。
        """

        self.arm = Arm()
        retry_count = 0

        while True:
            try:
                logger.info(
                    f"尝试连接机器人 {self.robot_ip} (第 {retry_count + 1} 次)..."
                )
                ret = self.arm.connect(self.robot_ip)
                if ret != StatusCodeEnum.OK:
                    logger.warning(f"连接失败: {ret.errmsg}")
                    retry_count += 1
                    continue

                logger.info("机器人连接成功")
                break

            except Exception as e:
                logger.error(f"连接循环异常: {e}")

            finally:
                self.arm.disconnect()
                logger.info("断开连接，等待重试...")
                retry_count += 1

        await self.arm.sub_pub.connect()
        await self.arm.sub_pub.subscribe_status(
            [
                RobotTopicType.CARTESIAN_POSITION,
                RobotTopicType.TP_PROGRAM_STATUS,
            ],
            frequency=200,
        )
        await self.arm.sub_pub.start_receiving(self.handle_robot_message)
        logger.info("状态订阅成功，开始接收消息")

        await self.arm.sub_pub.handle_receive_error()
