import httpx
import os

class WeChatAPI:
    def __init__(self):
        self.corpid = os.getenv("CORPID")
        self.secret = os.getenv("CORPSECRET")
        self.agentid = int(os.getenv("AGENTID"))

    async def get_token(self):
        url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corpid}&corpsecret={self.secret}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
            return resp.json().get("access_token")

    async def send_text_msg(self, touser: str, content: str):
        token = await self.get_token()
        url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}"
        data = {
            "touser": touser,
            "msgtype": "text",
            "agentid": self.agentid,
            "text": {"content": content}
        }
        async with httpx.AsyncClient() as client:
            await client.post(url, json=data)