# ~/secretary/scripts/weekly_summary.py
import asyncio
from datetime import datetime
import pytz
from openai import AsyncOpenAI
from mongo_client import summary_db
from dotenv import load_dotenv
import os

load_dotenv()

# ===================== 配置 =====================
TIMEZONE = pytz.timezone("Asia/Shanghai")

# AI 接口配置
API_BASE = os.getenv("DEEPSEEK_API_URL")
API_KEY = os.getenv("DEEPSEEK_API_KEY")

# AI 生成300字周总结
async def generate_weekly_summary(daily_list):
    client = AsyncOpenAI(base_url=API_BASE, api_key=API_KEY)
    content = "\n".join([f"{item['date']}：{item['content']}" for item in daily_list])
    prompt = f"""请以「技术学习+技术工作量」为核心，合并以下7天的记录，用不多于400字客观总结，仅保留技术相关事实，严格排除非技术内容（如非技术类读书、闲聊、无关日常等），不添加主观评价，逻辑清晰、重点突出。参考：
1.  技术学习累计成果，这周正在完成的项目有哪些什么（名称）
2.  技术工作量：具体技术工作内容、项目开发（技术模块）推进情况；
3.  完成与问题：本周技术相关计划是否达标，技术学习/工作中遇到的问题；
4.  关键细节：仅提炼与技术学习、技术工作相关的调整动作（如调整技术学习重点、优化项目开发节奏。
5. 无关内容一律不提取,如果全称没有技术内容，则无需导出
{content}"""
    response = await client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# 主函数
async def main():
    # 获取最近7天每日总结
    daily_list = summary_db.get_recent_7days()
    if not daily_list:
        print("❌ 近7天无每日摘要，无法生成周总结")
        return
    
    # 生成周总结
    weekly_summary = await generate_weekly_summary(daily_list)
    
    # ===================== 核心修改：自动生成周标识 + 独立保存 =====================
    # 格式：2026-W13（年份-第几周），唯一不重复
    week_tag = datetime.now(TIMEZONE).strftime("%Y-W%U")
    summary_db.save_weekly_summary(week_tag, weekly_summary)
    
    print(f"✅ {week_tag} 每周摘要已独立保存至 weekly_summaries 集合")

if __name__ == "__main__":
    asyncio.run(main())