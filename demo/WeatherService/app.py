import os
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests

# 动态获取端口号，普通服务的端口为自动分配
PORT = os.getenv("PORT", 8000)


logger = logging.getLogger(__name__)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/weather")
async def get_weather():
    """
    获取指定城市的天气
    :param city: 城市名
    :return: 城市天气信息
    """
    # 构建查询 URL
    url = f'http://t.weather.sojson.com/api/weather/city/101030100'
    try:
        response = requests.get(url)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="请求天气数据失败")

        # 返回的数据是字符串，直接返回给客户端
        weather_info = response.json()

        return {"weather": weather_info}

    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail="请求外部天气服务失败")

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
    )

    uvicorn.run(app, host="0.0.0.0", port=int(PORT))
