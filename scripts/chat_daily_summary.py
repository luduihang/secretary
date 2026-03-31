# ~/secretary/scripts/chat_daily_summary.py
import os
import asyncio
from datetime import datetime, timedelta
import pytz
from openai import AsyncOpenAI
from dotenv import load_dotenv
# 导入同目录的数据库客户端（核心：复用你的MongoDB连接）
from mongo_client import summary_db

# 加载环境变量
load_dotenv()

# ===================== 固定配置 =====================
TIMEZONE = pytz.timezone("Asia/Shanghai")
USER_ID = "LuDunHang"
# AI 接口配置
API_BASE = os.getenv("DEEPSEEK_API_URL")
API_KEY = os.getenv("DEEPSEEK_API_KEY")

# ===================== 1. 读取今日所有对话（从 MongoDB conversations 集合） =====================
def get_today_chat_records():
    """
    直接通过 mongo_client 连接，读取今日所有对话记录
    时间范围：当天 00:00 ~ 23:59（Asia/Shanghai 时区）
    排序：按时间正序（从早到晚）
    """
    # 直接访问 conversations 集合（复用你的数据库连接）
    conversations_col = summary_db.db["conversations"]
    
    now = datetime.now(TIMEZONE)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0) 
    end_of_day = start_of_day + timedelta(days=1)
    
    # 查询条件：匹配你的 user_id + 今日时间范围
    query = {
        "user_id": USER_ID,
        "timestamp": {"$gte": start_of_day, "$lt": end_of_day}
    }
    
    # 按 timestamp 正序排列（保证对话顺序正确）
    records = list(conversations_col.find(query).sort("timestamp", 1))
     # ===================== 调试代码：开始 =====================
    print(f"\n📊 今日读取到对话总条数：{len(records)}")
    print("-" * 50)
    for idx, rec in enumerate(records):
        time_str = rec["timestamp"].strftime("%H:%M")
        role = "用户" if rec["role"] == "user" else "AI"
        content_preview = rec["content"][:30] + "..." if len(rec["content"]) > 30 else rec["content"]
        print(f"【第{idx+1}条】[{time_str}] {role}：{content_preview}")
    print("-" * 50 + "\n")
    # ===================== 调试代码：结束 =====================

    return records

# ===================== 2. 格式化对话为 AI 易读文本 =====================
def format_chat_records(records):
    """
    把 MongoDB 对话记录格式化为纯文本
    示例：[09:33] 用户：你好你知道麦克斯韦方程组吗
          [09:33] AI：麦克斯韦方程组是...
    """
    if not records:
        return "今日无对话记录"
    
    parts = []
    for rec in records:
        time_str = rec["timestamp"].strftime("%H:%M")
        role = "用户" if rec["role"] == "user" else "AI"
        parts.append(f"[{time_str}] {role}：{rec['content']}")
    return "\n".join(parts)

# ===================== 3. AI 生成技术向每日摘要 =====================
async def generate_chat_daily_summary(chat_text):
    """
    严格过滤非技术内容，只保留技术学习/工作相关总结，字数≤120字
    """
    client = AsyncOpenAI(base_url=API_BASE, api_key=API_KEY)
    prompt = f"""请以「技术学习+技术工作量」为核心，从今日对话中用不多于200字提取,侧重于我个人主观上对于技术学习的个人倾向和个人安排，严格排除文学/物理/数学/闲聊等非技术内容，仅参考保留以下事实，若无技术对话则无需导出，参考：
1. 当前正在完成的项目名字是什么
2. 当前技术学习的知识点：比如Java/Python/框架/算法/技术问题探讨
3. 完成情况：技术任务进度/未完成原因
4. 我当前个人对于任务完成重点的倾向，情感，难易程度的判断
5. 无关内容一律不提取 
{chat_text}"""
    
    response = await client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ===================== 4. 主函数：读取→格式化→生成→保存 =====================
async def main():
    # 1. 拉取今日对话
    records = get_today_chat_records()
    # 2. 格式化为文本
    chat_text = format_chat_records(records)
    # 3. 生成技术向摘要
    summary = await generate_chat_daily_summary(chat_text)
    # 4. 保存到独立集合 chat_daily_summaries
    date_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    summary_db.save_chat_daily_summary(date_str, summary)
    
    print(f"✅ {date_str} 对话每日摘要已保存至 `chat_daily_summaries`")

if __name__ == "__main__":
    asyncio.run(main())