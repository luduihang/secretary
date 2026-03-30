# ~/code/python/secretary/utils/db.py

import os
import logging
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Optional
from pymongo import MongoClient
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MongoDBHandler:
    """
    MongoDB数据库管理器（优化版）
    统一管理：连接、对话存储、历史查询、任务管理
    """
    
    # 单例模式（全局使用一个数据库连接）
    _instance = None
    _client = None
    _db = None
    
    def __new__(cls):
        """单例构造"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化数据库连接（只执行一次）"""
        # 防止重复创建连接
        if self._client is not None:
            return
        
        mongo_uri = os.getenv("MONGO_URI")
        db_name = os.getenv("MONGO_DB", "personal_ai")
        
        if not mongo_uri:
            logger.error("MONGO_URI环境变量未设置")
            raise ValueError("MONGO_URI环境变量未设置")
        
        try:
            # 连接到MongoDB
            self._client = MongoClient(mongo_uri)
            self._db = self._client[db_name]
            
            # 创建索引（优化查询性能）
            self._db.conversations.create_index([("user_id", 1), ("timestamp", -1)])
            self._db.task_lifecycle.create_index([("user_id", 1), ("task_desc", 1)])
            
            logger.info(f"✅ MongoDB连接成功：{db_name}")
            
        except Exception as e:
            logger.error(f"数据库连接失败：{str(e)}")
            raise
    
    # 公共方法（暴露给外部使用）
    @property
    def conversations(self):
        """对话记录表"""
        return self._db["conversations"]
    
    @property
    def tasks(self):
        """任务状态表"""
        return self._db["task_lifecycle"]
    
    def insert_conversation(self, user_id: str, role: str, content: str) -> str:
        """
        保存一条对话记录
        
        Args:
            user_id: 用户ID（固定值，如 "kipley"）
            role: 角色（"user" 或 "assistant"）
            content: 对话内容
        
        Returns:
            插入的记录ID
        """
        try:
            document = {
                "user_id": user_id,
                "role": role,
                "content": content,
                "timestamp": datetime.now(pytz.timezone('Asia/Shanghai')),
                "created_at": datetime.now(pytz.timezone('Asia/Shanghai'))
            }
            
            result = self.conversations.insert_one(document)
            logger.info(f"💾 保存对话：{role} - {content[:50]}...")
            
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"对话保存失败：{str(e)}")
            return None
    
    def get_conversation_context(self, user_id: str, days: int = 7) -> str:
        """
        获取对话上下文字符串（AI直接可用）
        
        Args:
            user_id: 用户ID
            days: 查询天数（默认7天）
        
        Returns:
            格式化的对话历史字符串
        """
        conversations = self.get_conversation_history(user_id, days)
        
        if not conversations:
            return "（暂无对话历史）"
        
        # 格式化为对话历史
        context_parts = []
        for conv in conversations:
            role_label = "用户" if conv["role"] == "user" else "AI"
            content_preview = conv['content'][:100] + "..." if len(conv['content']) > 100 else conv['content']
            timestamp_str = conv['timestamp'].strftime("%m-%d %H:%M")
            context_parts.append(f"[{timestamp_str}] {role_label}：{content_preview}")
        
        context = "\n".join(context_parts)
        
        header = f"""以下是最近{days}天的对话历史：

---"""
        footer = f"""--- 以上为历史对话，请根据以上上下文回复用户的新问题。"""
        
        return header + context + footer
    
    def get_recent_conversation(self, user_id: str, max_rounds: int = 10) -> str:
        """
        🔥 滑动窗口核心方法：获取【最近N轮对话】上下文（最优上下文方案）
        一轮 = 用户1条 + AI1条，默认保留最近10轮（20条消息）
        固定Token消耗，永不爆炸！
        """
        try:
            # 最多获取 2*N 条消息（用户+AI）
            max_messages = max_rounds * 2
            # 查询：按时间【倒序】取最新的N轮，再【正序】排列（AI需要顺序阅读）
            cursor = self.conversations.find({
                "user_id": user_id
            }).sort("timestamp", -1).limit(max_messages)
            
            # 反转：让历史从早到晚排序（关键！否则对话顺序颠倒）
            messages = list(cursor)[::-1]

            if not messages:
                return "（暂无对话历史）"

            # 格式化上下文
            context_parts = []
            for msg in messages:
                role = "用户" if msg["role"] == "user" else "AI"
                context_parts.append(f"{role}：{msg['content']}")

            context = "\n".join(context_parts)
            return f"历史对话：\n{context}\n------------------------"

        except Exception as e:
            logger.error(f"滑动窗口查询失败：{str(e)}")
            return "（暂无对话历史）"
    
    def save_task(self, user_id: str, task_desc: str, ai_comment: str = "") -> str:
        """
        保存任务
        
        Args:
            user_id: 用户ID
            task_desc: 任务描述
            ai_comment: AI的评论
        
        Returns:
            任务ID
        """
        try:
            document = {
                "user_id": user_id,
                "task_desc": task_desc,
                "ai_comment": ai_comment,
                "status": "pending",
                "created_at": datetime.now(pytz.timezone('Asia/Shanghai')),
                "updated_at": datetime.now(pytz.timezone('Asia/Shanghai'))
            }
            
            result = self.tasks.update_one(
                {"user_id": user_id, "task_desc": task_desc},
                {
                    "$set": {
                        "status": "pending",
                        "created_at": datetime.now(pytz.timezone('Asia/Shanghai')),
                        "updated_at": datetime.now(pytz.timezone('Asia/Shanghai')),
                        "ai_comment": ai_comment
                    }
                },
                upsert=True  # 如果不存在则创建
            )
            
            logger.info(f"📋 创建/更新任务：{task_desc[:50]}...")
            
            return str(result.upserted_id)
            
        except Exception as e:
            logger.error(f"任务保存失败：{str(e)}")
            return None
    
    def update_task_status(self, user_id: str, task_desc: str, status: str, ai_comment: str = "") -> bool:
        """
        更新任务状态
        
        Args:
            user_id: 用户ID
            task_desc: 任务描述
            status: 新状态（pending, in_progress, completed）
            ai_comment: AI的评论
        
        Returns:
            是否成功
        """
        try:
            self.tasks.update_one(
                {"user_id": user_id, "task_desc": task_desc},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.now(pytz.timezone('Asia/Shanghai')),
                        "ai_comment": ai_comment
                    }
                }
            )
            
            logger.info(f"✅ 更新任务状态：{status}")
            return True
            
        except Exception as e:
            logger.error(f"任务更新失败：{str(e)}")
            return False
    
    def get_pending_tasks(self, user_id: str) -> List[Dict]:
        """
        获取待办任务
        
        Args:
            user_id: 用户ID
        
        Returns:
            待办任务列表
        """
        try:
            tasks = list(self.tasks.find({
                "user_id": user_id,
                "status": {"$in": ["pending", "in_progress"]}
            }).sort("created_at", -1))
            
            logger.info(f"📚 读取待办任务：{len(tasks)}个")
            return tasks
            
        except Exception as e:
            logger.error(f"待办查询失败：{str(e)}")
            return []
    
    def get_all_tasks(self, user_id: str) -> List[Dict]:
        """
        获取所有任务（包括已完成）
        
        Args:
            user_id: 用户ID
        
        Returns:
            所有任务列表
        """
        try:
            return list(self.tasks.find({"user_id": user_id}).sort("created_at", -1))
            
        except Exception as e:
            logger.error(f"所有任务查询失败：{str(e)}")
            return []
    
    def close(self):
        """关闭数据库连接"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            logger.info("🔌 MongoDB连接已关闭")

# 单例获取函数
def get_db_handler() -> MongoDBHandler:
    """
    获取数据库处理单例
    """
    if MongoDBHandler._instance is None:
        MongoDBHandler._instance = MongoDBHandler()
    return MongoDBHandler._instance

