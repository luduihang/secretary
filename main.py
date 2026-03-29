from fastapi import FastAPI, Request, BackgroundTasks, Query
from wechat_crypt import WXBizMsgCrypt
from utils.wechat_api import WeChatAPI
from core.ai_engine import AIEngine
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# 初始化模块
crypt = WXBizMsgCrypt(os.getenv("WECHAT_TOKEN"), os.getenv("ENCODING_AES_KEY"), os.getenv("CORPID"))
wechat = WeChatAPI()
ai = AIEngine()

async def process_ai_task(user_id: str, content: str):
    """后台异步处理 AI 逻辑并推送结果"""
    answer = await ai.get_ai_response(content, user_id)
    await wechat.send_text_msg(user_id, answer)


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
    
    print("plain_xml:", plain_xml)  # 调试输出解密后的明文
    if not plain_xml:
        return "decrypt error"

    msg_tree = ET.fromstring(plain_xml)
    print("msg_tree:", ET.tostring(msg_tree, encoding='utf-8').decode('utf-8'))  # 调试输出消息树内容
    user_id = msg_tree.find("FromUserName").text
    content = msg_tree.find("Content").text

    print("user_id:", user_id)  # 调试输出用户 ID
    print("content:", content)  # 调试输出消息内容

    # 3. 核心：异步处理
    background_tasks.add_task(process_ai_task, user_id, content)
    
    return "success"

if __name__ == "__main__":
    import uvicorn
    # 使用 uvicorn 运行，支持高并发异步
    uvicorn.run(app, host="0.0.0.0", port=8000)