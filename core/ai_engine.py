import sys
from openai import AsyncOpenAI
from utils.db import get_db_handler
# 导入你整合好的数据库客户端
from scripts.mongo_client import summary_db
import traceback
import re
import os
from datetime import datetime, timedelta
import pytz

# 固定配置（和你的数据库完全一致）
TIMEZONE = pytz.timezone("Asia/Shanghai")
USER_ID = "LuDunHang"

class AIEngine:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=os.getenv("NEWAPI_URL"),
            api_key=os.getenv("NEWAPI_KEY")
        )
        self.db = get_db_handler()

    # ===================== 工具函数：Markdown 转 企业微信纯文本（完全不变） =====================
    def format_markdown_for_wechat(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'^\s*[-=]{3,}\s*$', '━━━━━━━━━━━━', text, flags=re.MULTILINE)
        text = re.sub(r'#{1,4}\s+(.+)', r'【\1】', text)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'^\*\s', '• ', text, flags=re.MULTILINE)
        text = re.sub(r'^-\s', '• ', text, flags=re.MULTILINE)
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = text.replace('`', '')
        text = re.sub(r'\n\s*\n', '\n', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    # ===================== 新增：获取 昨日日期（你的日总结是前一天的） =====================
    def get_yesterday_date(self):
        """获取昨日日期字符串：2026-03-30"""
        today = datetime.now(TIMEZONE)
        yesterday = today - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")

    # ===================== 新增：获取所有背景总结（笔记+对话 周/日） =====================
    def get_all_summaries(self):
        """
        获取4份核心背景总结：
        1. 笔记周总结  2. 对话周总结
        3. 笔记日总结  4. 对话日总结
        """
        try:
            # 1. 获取周总结（最新）
            weekly_note = summary_db.get_latest_weekly()
            weekly_chat = summary_db.get_latest_chat_weekly()
            
            # 2. 🔥 新增：获取最近3天笔记总结
            recent_3notes = summary_db.get_recent_3days_notes()
            note_text = "\n".join([
                f"📅 {n['date']}：{n['content']}" 
                for n in recent_3notes
            ]) if recent_3notes else "暂无近3天笔记记录"

            # 3. 🔥 新增：获取最近3天对话总结
            recent_3chats = summary_db.get_recent_3days_chats()
            chat_text = "\n".join([
                f"📅 {c['date']}：{c['content']}" 
                for c in recent_3chats
            ]) if recent_3chats else "暂无近3天对话记录"

            return weekly_note, weekly_chat, note_text, chat_text
        except Exception as e:
            traceback.print_exc()
            return "获取失败", "获取失败", "获取失败", "获取失败"

    # ===================== 主对话函数（上下文已改造完成） =====================
    async def stream_ai_response(self, prompt: str, user_id: str):
        try:
            # 1. 获取最近8轮对话（原有滑动窗口）
            context = self.db.get_recent_conversation(user_id, max_rounds=8)

            # 2. 🔥 获取所有背景总结（核心新增）
            weekly_note, weekly_chat, note_text, chat_text = self.get_all_summaries()
            
            # 3. 🔥 拼接最终上下文（规范格式，AI最优理解）
# 3. 🔥 优化版上下文：学习管家角色 + 精简指令 + 进度背景
            full_context = f"""【角色定位】你是我的专属技术学习管家，核心职责：
1. 基于我的技术学习/工作进度，制定精简可行的任务计划
2. 跟进任务完成情况，针对性督促执行
3. 结合我的反馈实时调整安排，回答极简、聚焦任务，不冗余闲聊
4. 仅围绕Java/Python/项目开发/技术学习相关内容响应

【我的本周技术整体进度】
笔记总结：{weekly_note}
对话总结：{weekly_chat}

【我的昨日技术完成情况】
笔记总结：{note_text}
对话总结：{chat_text}

【近期沟通记录】
{context}

【我的当前反馈/需求】
{prompt}

请按管家职责，极简回复，聚焦任务安排与督促。
"""

            # 开启流式请求（使用拼接好的上下文）
            stream = await self.client.chat.completions.create(
                model="qwen-max",
                messages=[{"role": "user", "content": full_context}],
                stream=True
            )

            full_content = ""
            cache = ""
            sentence_enders = {"。", "！", "？", "；", "!", "?", "-"}
            MIN_CACHE = 80
            MAX_CACHE = 300

            async for chunk in stream:
                choices = chunk.get('choices') if isinstance(chunk, dict) else getattr(chunk, 'choices', [])
                if not choices:
                    continue
                first_choice = choices[0]
                delta = getattr(first_choice, 'delta', None)
                if delta is None:
                    continue
                content = getattr(delta, 'content', None)
                if not content:
                    continue

                full_content += content
                cache += content

                if len(cache) < MIN_CACHE:
                    continue
                if MIN_CACHE <= len(cache) < MAX_CACHE and cache[-1] in sentence_enders:
                    formatted_text = self.format_markdown_for_wechat(cache)
                    yield formatted_text
                    cache = ""
                    continue
                if len(cache) >= MAX_CACHE:
                    formatted_text = self.format_markdown_for_wechat(cache)
                    yield formatted_text
                    cache = ""

            if cache.strip():
                formatted_text = self.format_markdown_for_wechat(cache)
                yield formatted_text

            # 保存对话（原有逻辑不变）
            self.db.insert_conversation(user_id, "user", prompt)
            self.db.insert_conversation(user_id, "assistant", full_content)

        except Exception as e:
            traceback.print_exc()
            yield f"Error: {str(e)}"