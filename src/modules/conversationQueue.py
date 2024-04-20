import asyncio
import json
from datetime import datetime

class ConversationQueue():
    def __init__(self, bot):
        self.queue = asyncio.Queue()
        self.conversation_logs = {}
        self.bot = bot

    async def add_conversation(self, channel_id, user_id, message, role):
        conversation_id = f"{channel_id}_{user_id}"
        if conversation_id not in self.conversation_logs:
            self.conversation_logs[conversation_id] = {
                "channel_id": channel_id,
                "user_id": user_id,
                "messages": []
            }
            self.save_conversation_log(conversation_id)
        timestamp = datetime.now().isoformat()
        self.conversation_logs[conversation_id]["messages"].append({"role": role, "content": message, "timestamp": timestamp})
        self.save_conversation_log(conversation_id)
        await self.queue.put((conversation_id, message))

    async def get_conversation(self):
        conversation_id, message = await self.queue.get()
        return conversation_id, message

    def save_conversation_log(self, conversation_id):
        log_file = f"./logs/conversations/{conversation_id}.json"
        with open(log_file, "w") as f:
            json.dump(self.conversation_logs[conversation_id], f, indent=4)