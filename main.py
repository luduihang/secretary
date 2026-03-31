from fastapi import FastAPI, Request, BackgroundTasks, Query
from wechat_crypt import WXBizMsgCrypt
from utils.wechat_api import WeChatAPI
from core.ai_engine import AIEngine
import xml.etree.ElementTree as ET
import os
import asyncio  # 新增：控制发送间隔，防企业微信限流
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# 初始化模块
crypt = WXBizMsgCrypt(os.getenv("WECHAT_TOKEN"), os.getenv("ENCODING_AES_KEY"), os.getenv("CORPID"))
wechat = WeChatAPI()
ai = AIEngine()

async def process_ai_task(user_id: str, content: str):
    """
    🔥 改造：分段接收AI内容 → 分段推送企业微信
    接近流式体验，轻量服务器无压力
    """
    
    try:
        # 2. 遍历AI分段生成的内容，逐段推送
        async for segment in ai.stream_ai_response(content, user_id):
            if segment.strip():  # 过滤空内容
                await wechat.send_text_msg(user_id, segment)
                # 轻微延迟（可选），防止企业微信发送频率限制
                await asyncio.sleep(0.2)
        
        # 3. 最后推送完成提示（可选）
        await wechat.send_text_msg(user_id, "✅ 回复完毕")
    
    except Exception as e:
        await wechat.send_text_msg(user_id, f"❌ 服务异常：{str(e)}")


@app.get("/wechat")
async def verify(echostr: str = Query(None)):
    """处理企业微信后台的 URL 验证"""
    if echostr:
        # 修改点：解密返回的是元组 (明文, CorpID)，验证只需返回明文
        content, _ = crypt.decrypt(echostr) 
        print("echostr content:", content)  # 调试输出解密后的 echostr 内容
        return content
    return "Invalid Request"

@app.post("/wechat")
async def handle_message(request: Request, background_tasks: BackgroundTasks):
    """接收用户消息的主入口"""
    body = await request.body()
    
    # 1. 解析加密 XML
    xml_tree = ET.fromstring(body)
    encrypt_content = xml_tree.find("Encrypt").text
    
    # print("encrypt_content:", encrypt_content)  # 调试输出加密内容
    # 2. 解密
    # 修改点：解密返回的是元组，我们只需要第一个值 plain_xml
    plain_xml, _ = crypt.decrypt(encrypt_content)
    if not plain_xml:
        return "decrypt error"

    msg_tree = ET.fromstring(plain_xml)
    user_id = msg_tree.find("FromUserName").text
    content = msg_tree.find("Content").text

    # 3. 核心：异步处理
    background_tasks.add_task(process_ai_task, user_id, content)
    
    return "success"

if __name__ == "__main__":
    import uvicorn
    # 使用 uvicorn 运行，支持高并发异步
    uvicorn.run(app, host="0.0.0.0", port=8000)