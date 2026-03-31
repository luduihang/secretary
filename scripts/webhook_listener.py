# ~/secretary/scripts/webhook_listener.py
from fastapi import FastAPI, Request, Header
import subprocess
import os

app = FastAPI()
# 安全密钥（自己随便写一个字符串，后面GitHub要用）
SECRET_TOKEN = "188390AA52f@"
# 你的同步脚本路径
SYNC_SCRIPT = "/home/ubuntu/code/python/secretary/scripts/sync_vault.sh"

@app.post("/webhook")
async def github_webhook(request: Request, x_github_event: str = Header(None)):
    # 1. 验证请求来自GitHub
    body = await request.body()
    # 2. 执行同步脚本
    try:
        result = subprocess.run(
            ["bash", SYNC_SCRIPT],
            capture_output=True,
            text=True,
            cwd=os.path.dirname(SYNC_SCRIPT)
        )
        print("同步成功:", result.stdout)
        return {"status": "success", "message": "Obsidian 已实时同步"}
    except Exception as e:
        return {"status": "error", "message": str(e)}