"""
HTTP/WebSocket 层使用的 Pydantic 模型。
"""

from typing import Optional, Literal
from enum import Enum

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """WebSocket 推送的消息类别。"""

    TCP_VELOCITY = "tcp_velocity"
    RUNNING_PROGRAM = "running_program"


class Position(BaseModel):
    """TCP 末端在笛卡尔坐标系下的位姿，单位：mm。"""

    x: float = Field(..., description="X 轴坐标，单位 mm")
    y: float = Field(..., description="Y 轴坐标，单位 mm")
    z: float = Field(..., description="Z 轴坐标，单位 mm")


class TcpVelocityMessage(BaseModel):
    """
    发送到 WebSocket 客户端的“TCP 末端速度”消息。
    """

    type: MessageType = Field(
        default=MessageType.TCP_VELOCITY, description="消息类型标识"
    )
    velocity: float = Field(..., description="TCP 末端速度，单位 mm/s")
    unit: Literal["mm/s"] = Field(default="mm/s", description="速度单位")
    position: Optional[Position] = Field(default=None, description="末端坐标，可为空")


class RunningProgramMessage(BaseModel):
    """
    WebSocket 推送的“当前运行程序”消息。

    主要用于 UI 上展示正在运行的 TP 程序名称。
    """

    type: MessageType = Field(
        default=MessageType.RUNNING_PROGRAM, description="消息类型标识"
    )
    program_name: str = Field(..., description="机器人端当前运行的程序名称")


class SetTcpVelocityIndexRequest(BaseModel):
    """
    HTTP `/api/set_tcp_velocity_r_index` 接口的请求体验证模型。
    """

    index: int = Field(..., description="R 寄存器编号")
