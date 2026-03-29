from openai import AsyncOpenAI
import os

class AIEngine:
    def __init__(self):
        self.client = AsyncOpenAI(
            base_url=os.getenv("NEWAPI_URL"),
            api_key=os.getenv("NEWAPI_KEY")
        )

    async def get_ai_response(self, prompt: str, user_id: str):
        # TODO: 这里可以写数据库查询，获取 user_id 的历史上下文
        try:
            response = await self.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}"