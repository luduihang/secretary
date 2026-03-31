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
        🔥 通用终极版：AI逻辑分点优先 + 企业微信纯文本美化
        1. 完整保留 1.2.3. / 序号 / 分点结构（核心！）
        2. 清理所有Markdown冗余符号
        3. 美化分隔线、标题、排版
        4. 全场景适配（日常/学术/代码/问答）
        """
        if not text:
            return ""
        
        # 1. 处理分隔线 --- 转为企业微信优雅分割线（区块分隔）
        text = re.sub(r'^\s*[-=]{3,}\s*$', '━━━━━━━━━━━━', text, flags=re.MULTILINE)
        
        # 2. 处理标题 # → 简洁【标题】格式（不夸张，通用美观）
        text = re.sub(r'#{1,4}\s+(.+)', r'【\1】', text)
        
        # 3. 移除粗体 ** ** （保留文字，去掉符号）
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        
        # 4. 保留所有分点格式：1. 2. 3. / - / * （完全不修改AI原生分点）
        # 仅美化无序列表符号，更美观
        text = re.sub(r'^\*\s', '• ', text, flags=re.MULTILINE)
        text = re.sub(r'^-\s', '• ', text, flags=re.MULTILINE)
        
        # 5. 清理代码块、冗余符号
        text = re.sub(r'```[\s\S]*?```', '', text)  # 移除代码块
        text = text.replace('`', '')  # 移除行内代码符号
        
        # 6. 优化排版：清理多余空行，保证分点清晰、不松散
        text = re.sub(r'\n\s*\n', '\n', text)  # 合并空行
        text = re.sub(r' +', ' ', text)  # 合并多余空格
        
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
            MIN_CACHE = 80   # 最小80字
            MAX_CACHE = 300  # 最大120字
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