from openai import AsyncOpenAI
from utils.db import get_db_handler
import traceback
import re
import os

class AIEngine:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=os.getenv("NEWAPI_URL"),
            api_key=os.getenv("NEWAPI_KEY")
        )
        self.db = get_db_handler()

    # ===================== 工具函数：Markdown 转 企业微信纯文本 =====================
    def format_markdown_for_wechat(self, text: str) -> str:
        """
        企业微信不支持Markdown，转换为美观纯文本
        修复标题、粗体、列表、代码块、换行等格式问题
        """
        if not text:
            return text
        
        # 1. 移除标题符号 # → 换成【】+换行
        text = re.sub(r'### (.*?)\n', r'【\1】\n', text)
        text = re.sub(r'## (.*?)\n', r'【\1】\n', text)
        text = re.sub(r'# (.*?)\n', r'【\1】\n', text)
        
        # 2. 移除粗体 ** **
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
        
        # 3. 列表符号 -/* → 改为 ▶️ 更美观
        text = re.sub(r'^- ', '▶️ ', text, flags=re.MULTILINE)
        text = re.sub(r'^\* ', '▶️ ', text, flags=re.MULTILINE)
        
        # 4. 移除代码块```，替换为标识
        text = re.sub(r'```.*?\n', '', text)
        text = text.replace('```', '')
        
        # 5. 清理多余空行，保证微信阅读舒适
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()

    async def stream_ai_response(self, prompt: str, user_id: str):
        try:
            context = self.db.get_recent_conversation(user_id, max_rounds=8)
            full_prompt = f"{context}\n\n用户当前问题：{prompt}"

            # 开启流式
            stream = await self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": full_prompt}],
                stream=True
            )

            full_content = ""
            cache = ""
            # 句子结束符（语义分割）
            sentence_enders = {"。", "！", "？", "；", "!", "?", "-"}
            # ===================== 优化分段：100字左右区间（自然不生硬） =====================
            MIN_CACHE = 40   # 最小80字
            MAX_CACHE = 150  # 最大120字
            # 围绕 100 字，语义优先分段

            async for chunk in stream:
                content = chunk.choices[0].delta.content or ""
                if not content:
                    continue

                full_content += content
                cache += content

                # ===================== 核心：自然语义分段规则 =====================
                # 1. 小于80字：绝对不发送
                if len(cache) < MIN_CACHE:
                    continue
                
                # 2. 80~120字：遇到句子结束符 → 发送（语义优先）
                if MIN_CACHE <= len(cache) < MAX_CACHE and cache[-1] in sentence_enders:
                    # 发送前：转换Markdown为微信纯文本
                    formatted_text = self.format_markdown_for_wechat(cache)
                    yield formatted_text
                    cache = ""
                    continue
                
                # 3. 超过120字：强制发送（防止无限缓存）
                if len(cache) >= MAX_CACHE:
                    formatted_text = self.format_markdown_for_wechat(cache)
                    yield formatted_text
                    cache = ""

            # 最后兜底：发送剩余内容
            if cache.strip():
                formatted_text = self.format_markdown_for_wechat(cache)
                yield formatted_text

            # 保存完整对话
            self.db.insert_conversation(user_id, "user", prompt)
            self.db.insert_conversation(user_id, "assistant", full_content)

        except Exception as e:
            traceback.print_exc()
            yield f"Error: {str(e)}"