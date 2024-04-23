import asyncio
import os
import json
from loguru import logger
from datetime import datetime
from groq import Groq
from utils import load_config
from settings import load_settings

class RequestQueue():
    def __init__(self, bot):
        self.queue = asyncio.Queue()
        self.conversation_logs = {}
        self.bot = bot
        self.llm_client = Groq(api_key=os.getenv('GROQ_API_KEY'))


    async def add_conversation(self, channel_id, user_id, message, role, create_empty=False):
        conversation_id = f"{channel_id}_{user_id}"
        settings = load_settings("./src/settings/user_settings.json")  # Load settings

        if conversation_id not in self.conversation_logs:
            timestamp = datetime.now().isoformat()
            self.conversation_logs[conversation_id] = {
                "channel_id": channel_id,
                "user_id": user_id,
                "timestamp": timestamp,
                "model": settings["model"]["value"],
                "temperature": settings["temperature"]["value"],
                "max_tokens": settings["max_tokens"]["value"],
                "system_prompt": settings["system_prompt"]["value"],
                "messages": [{"role": "system", "content": settings["system_prompt"]["value"]}]
            }
        if not create_empty:
            self.conversation_logs[conversation_id]["messages"].append({"role": role, "content": message})
            self.save_conversation_log(conversation_id)
            await self.queue.put((conversation_id, message))
        else:
            self.save_conversation_log(conversation_id)
            

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
                temperature=conversation_log["temperature"],
                max_tokens=conversation_log["max_tokens"],
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
        log_folder = "./logs/conversations"
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        log_file = f"{log_folder}/{conversation_id}.json"
        with open(log_file, "w") as f:
            json.dump(self.conversation_logs[conversation_id], f, indent=4)

    def clear_conversation_log(self, conversation_id, user_id):
        log_file = f"./logs/conversations/{conversation_id}.json"
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    conversation_log = json.load(f)
                    if conversation_log["user_id"] == user_id:
                        if self.queue.qsize() == 0:
                            self.conversation_logs.pop(conversation_id, None)
                            f.close()
                            os.remove(log_file)
                            logger.info(f"Conversation log cleared for {conversation_id}.")
                            return "Conversation log cleared."
                        else:
                            return "Cannot clear conversation log while messages are in the queue."
                    else:
                        return "You can only clear conversations that you started."
            except Exception as e:
                logger.error(f"Failed to clear conversation log for {conversation_id}: {e}")
                return "Failed to access or clear the conversation log due to an error."
        else:
            logger.error(f"Conversation log file not found for {conversation_id}.")
            return "No conversation log file found."
