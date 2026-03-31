from pymongo import MongoClient
from datetime import datetime
import pytz

# ===================== 你的MongoDB真实配置 =====================
MONGO_URI = "mongodb://kipleyarch:188390AA52f%40@127.0.0.1:27017/?authSource=admin"
MONGO_DB = "personal_ai"
USER_ID = "LuDunHang"
TIMEZONE = pytz.timezone("Asia/Shanghai")

# ===================== 四大独立集合（笔记 + 对话 完全分离） =====================
# 原有：笔记总结（不动，兼容旧代码）
COLLECTION_DAILY = "note_daily_summaries"       # 笔记每日总结
COLLECTION_WEEKLY = "note_weekly_summaries"     # 笔记每周总结
# 新增：对话总结（全新专用）
COLLECTION_CHAT_DAILY = "chat_daily_summaries"   # 对话每日总结
COLLECTION_CHAT_WEEKLY = "chat_weekly_summaries" # 对话每周总结

class SummaryDBClient:
    
    def __init__(self):
        # 不立即连接！只保存配置
        self._client = None
        self._db = None

    @property
    def client(self):
        if self._client is None:
            # 第一次访问时才连接
            self._client = MongoClient(MONGO_URI)
        return self._client

    @property
    def db(self):
        if self._db is None:
            self._db = self.client[MONGO_DB]
        return self._db

    @property
    def daily_col(self):
        return self.db[COLLECTION_DAILY]

    @property
    def weekly_col(self):
        return self.db[COLLECTION_WEEKLY]

    @property
    def chat_daily_col(self):
        return self.db[COLLECTION_CHAT_DAILY]

    @property
    def chat_weekly_col(self):
        return self.db[COLLECTION_CHAT_WEEKLY]

    # ===================== 原有：笔记总结方法（完全不动，兼容旧脚本） =====================
    def save_daily_summary(self, date_str: str, content: str):
        self.daily_col.update_one(
            {"user_id": USER_ID, "date": date_str},
            {"$set": {"user_id": USER_ID,"date": date_str,"content": content,"update_time": datetime.now(TIMEZONE)}},
            upsert=True
        )

    def get_recent_7days(self):
        return list(self.daily_col.find({"user_id": USER_ID}).sort("date", -1).limit(7))

    def save_weekly_summary(self, week_tag: str, content: str):
        self.weekly_col.update_one(
            {"user_id": USER_ID, "week": week_tag},
            {"$set": {"user_id": USER_ID,"week": week_tag,"content": content,"update_time": datetime.now(TIMEZONE)}},
            upsert=True
        )

    def get_latest_weekly(self):
        res = self.weekly_col.find_one({"user_id": USER_ID}, sort=[("week", -1)])
        return res["content"] if res else "暂无本周笔记总结"

    # ===================== 新增：对话每日总结方法 =====================
    def save_chat_daily_summary(self, date_str: str, content: str):
        """保存【对话】每日总结（永久保存，自动去重）"""
        self.chat_daily_col.update_one(
            {"user_id": USER_ID, "date": date_str},
            {"$set": {"user_id": USER_ID,"date": date_str,"content": content,"update_time": datetime.now(TIMEZONE)}},
            upsert=True
        )

    # ===================== 新增：获取最近3天总结（AI管家专用） =====================
    def get_recent_3days_notes(self):
        """获取最近3天【笔记】日总结，按日期倒序"""
        return list(self.daily_col.find(
            {"user_id": USER_ID}
        ).sort("date", -1).limit(3))

    def get_recent_3days_chats(self):
        """获取最近3天【对话】日总结，按日期倒序"""
        return list(self.chat_daily_col.find(
            {"user_id": USER_ID}
        ).sort("date", -1).limit(3))

    # ===================== 新增：获取最近7天总结（AI笔记总结梳理专用） =====================

    def get_recent_7days_chat(self):
        """获取【对话】最近7天总结（生成对话周总结用）"""
        return list(self.chat_daily_col.find({"user_id": USER_ID}).sort("date", -1).limit(7))

    # ===================== 新增：对话每周总结方法 =====================
    def save_chat_weekly_summary(self, week_tag: str, content: str):
        """保存【对话】每周总结（永久保存）"""
        self.chat_weekly_col.update_one(
            {"user_id": USER_ID, "week": week_tag},
            {"$set": {"user_id": USER_ID,"week": week_tag,"content": content,"update_time": datetime.now(TIMEZONE)}},
            upsert=True
        )

    def get_latest_chat_weekly(self):
        """获取【对话】最新一周总结（AI对话调用）"""
        res = self.chat_weekly_col.find_one({"user_id": USER_ID}, sort=[("week", -1)])
        return res["content"] if res else "暂无本周对话总结"

# 全局实例（所有脚本共用）
summary_db = SummaryDBClient()