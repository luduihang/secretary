# ~/secretary/scripts/chat_weekly_summary.py
import os
import asyncio
from datetime import datetime
import pytz
from openai import AsyncOpenAI
from dotenv import load_dotenv
# 导入同目录的数据库客户端
from mongo_client import summary_db

# 加载环境变量
load_dotenv()

# ===================== 固定配置（和每日总结完全一致） =====================
TIMEZONE = pytz.timezone("Asia/Shanghai")
USER_ID = "LuDunHang"
# AI 接口配置
API_BASE = os.getenv("DEEPSEEK_API_URL")
API_KEY = os.getenv("DEEPSEEK_API_KEY")

# ===================== 1. 获取最近7天对话每日总结 =====================
def get_weekly_chat_records():
    """
    从数据库获取最近7天的对话每日总结
    用于生成每周技术总结
    """
    # 复用mongo_client内置方法，获取7天对话日总结
    daily_records = summary_db.get_recent_7days_chat()

    # ===================== 调试代码：打印7天总结（和每日脚本对齐） =====================
    print(f"\n📊 读取到近7天对话日总结总数：{len(daily_records)}")
    print("-" * 50)
    for idx, rec in enumerate(daily_records):
        date_str = rec["date"]
        content_preview = rec["content"][:40] + "..." if len(rec["content"]) > 40 else rec["content"]
        print(f"【第{idx+1}天】{date_str}：{content_preview}")
    print("-" * 50 + "\n")
    # ===================== 调试代码结束 =====================

    return daily_records

# ===================== 2. 格式化7天总结文本 =====================
def format_weekly_records(records):
    if not records:
        return "近7天无对话技术总结"
    parts = []
    for rec in records:
        parts.append(f"【{rec['date']}】{rec['content']}")
    return "\n".join(parts)

# ===================== 3. AI生成对话每周技术总结 =====================
async def generate_chat_weekly_summary(weekly_text):
    """
    生成每周技术总结，严格过滤非技术内容，280-320字
    完全匹配你的需求：项目、技术学习、进度、个人倾向、问题
    """
    client = AsyncOpenAI(base_url=API_BASE, api_key=API_KEY)
    prompt = f"""请以「技术学习+技术工作量」为核心，合并近7天对话技术总结，用不多于400字客观总结，侧重于我个人主观上对于技术学习的个人倾向和个人安排,严格排除文学/物理/数学/闲聊等所有非技术内容，，若无技术对话则无需导出，仅保留以下核心信息：
1. 本周完成/进行中的技术项目名称与进度
2. 本周技术学习核心知识点（Java/Python/框架/算法/技术等问题）
3. 技术任务整体完成情况、未完成原因
4. 我当前个人对于任务完成重点的倾向，情感，难易程度的判断
5. 无关内容一律不提取
{weekly_text}"""

    response = await client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# ===================== 4. 主函数 =====================
async def main():
    # 1. 获取7天对话日总结
    daily_records = get_weekly_chat_records()
    if not daily_records:
        print("❌ 近7天无对话日总结，无法生成周总结")
        return

    # 2. 格式化文本
    weekly_text = format_weekly_records(daily_records)
    # 3. 生成周总结
    weekly_summary = await generate_chat_weekly_summary(weekly_text)
    # 4. 生成周标识（格式：2026-W13）
    week_tag = datetime.now(TIMEZONE).strftime("%Y-W%U")
    # 5. 保存到数据库
    summary_db.save_chat_weekly_summary(week_tag, weekly_summary)

    print(f"✅ {week_tag} 对话每周摘要已保存至 `chat_weekly_summaries`")

if __name__ == "__main__":
    asyncio.run(main())