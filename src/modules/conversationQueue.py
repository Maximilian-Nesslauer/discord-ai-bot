import asyncio
import os
import json
from datetime import datetime
from groq import Groq
from utils import load_config

class ConversationQueue():
    def __init__(self, bot):
        self.queue = asyncio.Queue()
        self.conversation_logs = {}
        self.bot = bot
        self.llm_client = Groq(api_key=os.getenv('GROQ_API_KEY'))


    async def add_conversation(self, channel_id, user_id, message, role):
        conversation_id = f"{channel_id}_{user_id}"
        if conversation_id not in self.conversation_logs:
            timestamp = datetime.now().isoformat()
            self.conversation_logs[conversation_id] = {
                "channel_id": channel_id,
                "user_id": user_id,
                "timestamp": timestamp,
                "model": "llama3-70b-8192",
                "messages": []
            }
            self.conversation_logs[conversation_id]["messages"].append({"role": "system", "content": "You are a highly skilled and helpful AI assistant."})
            self.save_conversation_log(conversation_id)
        self.conversation_logs[conversation_id]["messages"].append({"role": role, "content": message})
        self.save_conversation_log(conversation_id)
        await self.queue.put((conversation_id, message))

    async def get_conversation(self):
        conversation_id, message = await self.queue.get()
        return conversation_id, message

    async def process_conversation(self):
        while True:
            conversation_id, message = await self.get_conversation()
            conversation_log = self.conversation_logs[conversation_id]
            messages = conversation_log["messages"]

            # Call the API
            response = self.llm_client.chat.completions.create(
                messages=messages,
                model=conversation_log["model"],
                temperature=0.7,
                max_tokens=512,
                top_p=1,
                stream=False
            )

            answer = response.choices[0].message.content

            # Save the answer in the conversation log
            conversation_log["messages"].append({"role": "assistant", "content": answer})
            self.save_conversation_log(conversation_id)
            
            # Send the answer to Discord
            channel = self.bot.get_channel(conversation_log["channel_id"])

            # Split the answer into multiple messages to handle discord message limits
            chunks = [answer[i:i+1900] for i in range(0, len(answer), 1900)]
            for chunk in chunks:
                await channel.send(chunk)
            
    def save_conversation_log(self, conversation_id):
        log_file = f"./logs/conversations/{conversation_id}.json"
        with open(log_file, "w") as f:
            json.dump(self.conversation_logs[conversation_id], f, indent=4)