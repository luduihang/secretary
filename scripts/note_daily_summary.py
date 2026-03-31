# ~/secretary/scripts/daily_summary.py
import os
import asyncio
from datetime import datetime
import pytz
from openai import AsyncOpenAI
from mongo_client import summary_db
from dotenv import load_dotenv
import os

load_dotenv()

# ===================== 固定配置 =====================
VAULT_ROOT = os.path.expanduser("~/secretary/obsidian_vault")
TIMEZONE = pytz.timezone("Asia/Shanghai")

# AI 接口配置
API_BASE = os.getenv("DEEPSEEK_API_URL")
API_KEY = os.getenv("DEEPSEEK_API_KEY")

# 获取今日日志路径
def get_today_log_path():
    now = datetime.now(TIMEZONE)
    year = now.year
    month = now.month
    date_str = now.strftime("%Y-%m-%d")
    return os.path.join(VAULT_ROOT, "我的工作量", f"{year}年度", f"{month}月份", f"{date_str}.md")
    
# 读取日志内容
def read_today_log():
    log_path = get_today_log_path()
    print(log_path)
    if not os.path.exists(log_path):
        return "今日未记录学习/工作内容"
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "日志文件读取失败"

# AI 生成100字客观摘要
async def generate_daily_summary(text):
    client = AsyncOpenAI(base_url=API_BASE, api_key=API_KEY)
    prompt = f"""请以「技术学习+技术工作量」为核心，用不多于120字客观总结今日内容，仅保留技术相关事实，严格排除非技术内容（如非技术类读书、闲聊、无关日常等），不添加主观评价、不冗余。参考：
1. 当前正在完成的项目是什么（名称）
2. 当前技术学习的知识点：比如Java/Python/框架/算法/技术问题探讨
3. 完成情况：技术任务进度/未完成原因
4. 核心细节：仅提炼与技术学习、技术工作相关的关键内容，无关内容一律不提及。
5. 无关内容一律不提取,如果全程没有技术内容，则无需导出
{text}"""
    print(text)
    response = await client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# 主函数
async def main():
    log_content = read_today_log()
    if log_content == "今日未记录学习/工作内容":
        summary = log_content
    else:
        summary = await generate_daily_summary(log_content)
    date_str = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    
    # ===================== 核心修改：独立保存每日总结 =====================
    summary_db.save_daily_summary(date_str, summary)
    print(f"✅ {date_str} 每日摘要已独立保存至 daily_summaries 集合")

if __name__ == "__main__":
    asyncio.run(main())