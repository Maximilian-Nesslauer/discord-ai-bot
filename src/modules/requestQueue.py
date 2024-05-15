import asyncio
import os
import json
import shutil
import discord
from loguru import logger
from datetime import datetime
from utils import load_config
from settings import load_settings
from ModelClientHandler import ModelClientManager

settings = load_settings("./src/settings/user_settings.json")
log_folder = "./logs/conversations"

class RequestQueue():
    def __init__(self, bot):
        self.queue = asyncio.Queue() # Queue of (conversation_id, message, is_image_gen) tuples
        self.conversation_logs = {}
        self.bot = bot
        self.model_client_manager = ModelClientManager()

        self.config = load_config('./config.json')
        self.image_gen_trigger_words = self.config.get('image_gen_trigger_words', [])
        
    def load_conversation_logs(self):
        if os.path.exists(log_folder):
            for filename in os.listdir(log_folder):
                if filename.endswith(".json"):
                    log_file_path = os.path.join(log_folder, filename)
                    with open(log_file_path, "r") as file:
                        conversation_id = filename[:-5]  # Remove '.json' extension
                        self.conversation_logs[conversation_id] = json.load(file)
                        logger.info(f"Loaded conversation log for {conversation_id}")

    async def add_conversation(self, channel_id, user_id, message, role, message_id=None, create_empty=False):
        conversation_id = f"{channel_id}_{user_id}"
        timestamp = datetime.now().isoformat()

        if conversation_id not in self.conversation_logs:
            self.conversation_logs[conversation_id] = {
                "channel_id": channel_id,
                "user_id": user_id,
                "timestamp": timestamp,
                "model_text": settings["model_text"]["value"],
                "model_img": settings["model_img"]["value"],
                "character": "Assistant",
                "temperature": settings["temperature"]["value"],
                "max_tokens": settings["max_tokens"]["value"],
                "assistant_system_prompt": settings['characters']['Assistant']['system_prompt'],
                "messages": [{"role": "system", "content": settings['characters']['Assistant']['system_prompt'], "type": "character_msg"}]
            }

        if not create_empty:
            conversation_log = self.conversation_logs[conversation_id]
            channel = self.bot.get_channel(conversation_log["channel_id"])

            # if image prompt
            # Check if the message contains any image generation trigger word and ask the llm to confirm if an image needs to be generated
            if any(word in message.lower() for word in self.image_gen_trigger_words):
                # if llama3-8b via Groq is available use it, otherwise use the model of the current conversation
                model_settings = settings["model_text"]["choices"].get("llama3-8b-8192 (via Groq)", settings["model_text"]["choices"][self.conversation_logs[conversation_id]["model_text"]])
                response = self.model_client_manager.ask_if_generate_image(message, model_settings)

                if response.lower().strip() == 'yes':

                    try:
                        last_msg_id = conversation_log['messages'][-1]['message_ids'][-1]
                        if last_msg_id:
                            last_msg = await channel.fetch_message(last_msg_id)
                            for reaction in last_msg.reactions:
                                if reaction.emoji == '🔄' and reaction.me:
                                    await reaction.remove(self.bot.user)
                                if reaction.emoji == '🗑️' and reaction.me:
                                    await reaction.remove(self.bot.user)
                    except Exception as e:
                        logger.error(f"Failed to fetch or edit message for reaction removal: {e}")

                    message_entry = {"role": role, "content": message, "message_ids": []}
                    if role == 'user':
                        message_entry["message_ids"] = [message_id]
                    conversation_log["messages"].append(message_entry)
                    self.save_conversation_log(conversation_id)

                    # Pre-process image prompt
                    improved_prompt = self.model_client_manager.preprocess_image_prompt(conversation_log, model_settings)
                    await self.queue.put((conversation_id, improved_prompt, True))
                    return
                
            # elif text prompt
            # Delete the reactions from the last message
            try:
                last_msg_id = conversation_log['messages'][-1]['message_ids'][-1]
                if last_msg_id:
                    last_msg = await channel.fetch_message(last_msg_id)
                    for reaction in last_msg.reactions:
                        if reaction.emoji == '🔄' and reaction.me:
                            await reaction.remove(self.bot.user)
                        if reaction.emoji == '🗑️' and reaction.me:
                            await reaction.remove(self.bot.user)
            except Exception as e:
                logger.error(f"Failed to fetch or edit message for reaction removal: {e}")

            message_entry = {"role": role, "content": message, "message_ids": []}
            if role == 'user':
                message_entry["message_ids"] = [message_id]
            self.conversation_logs[conversation_id]["messages"].append(message_entry)
            self.save_conversation_log(conversation_id)
            await self.queue.put((conversation_id, message, False))
        else:
            self.save_conversation_log(conversation_id)

    async def get_conversation(self):
        conversation_id, message, is_image_gen = await self.queue.get()
        return conversation_id, message, is_image_gen

    async def process_conversation(self):
        while True:
            conversation_id, message, is_image_request = await self.get_conversation()
            conversation_log = self.conversation_logs[conversation_id]
            channel = self.bot.get_channel(conversation_log["channel_id"])

            if is_image_request:
                # Handle image generation
                prompt = message
                model_settings = settings["model_img"]["choices"][conversation_log["model_img"]]
                image_data = await self.model_client_manager.make_img_gen_call(prompt, model_settings)

                if image_data:
                    directory_path = f"./logs/conversations/img_{conversation_id}"
                    if not os.path.exists(directory_path):
                        os.makedirs(directory_path)

                    image_path = f"{directory_path}/{datetime.now().strftime('%Y-%m-%dT%H-%M-%S.%f')}.png"
                    
                    with open(image_path, 'wb') as f:
                        f.write(image_data)
                    message = await channel.send(file=discord.File(image_path))
                else:
                    await channel.send("Failed to generate image.")

                conversation_log["messages"].append({"role": "assistant", "content": "Sure! Here is your image with the prompt '{prompt}'). (The Image was send to the user using Stable Diffusion via an API)", "message_ids": message.id})

            else:
                # Handle text response
                messages = [{"role": msg["role"], "content": msg["content"]} for msg in conversation_log["messages"]]
                response = self.model_client_manager.make_llm_call(
                    messages=messages,
                    model_settings=settings["model_text"]["choices"][conversation_log["model_text"]],
                    temperature=conversation_log["temperature"],
                    max_tokens=conversation_log["max_tokens"],
                    top_p=1,
                    stream=False
                )

                response_message_ids = []

                chunks = [response[i:i+1900] for i in range(0, len(response), 1900)]
                for chunk in chunks:
                    message = await channel.send(chunk)
                    response_message_ids.append(message.id)

                conversation_log["messages"].append({"role": "assistant", "content": response, "message_ids": response_message_ids})

            await message.add_reaction('🔄')
            await message.add_reaction('🗑️')
            self.save_conversation_log(conversation_id)
            
    def save_conversation_log(self, conversation_id):
        if not os.path.exists(log_folder):
            os.makedirs(log_folder)
        log_file = f"{log_folder}/{conversation_id}.json"
        with open(log_file, "w") as f:
            json.dump(self.conversation_logs[conversation_id], f, indent=4)

    async def handle_reroll_reaction(self, message_id, user_id):
        for conversation_id, log in self.conversation_logs.items():
            for msg in log['messages']:
                if user_id == log['user_id'] and message_id in msg.get('message_ids', []):
                    is_active = any(item[0] == conversation_id for item in self.queue._queue)
                    if is_active:
                        logger.info("Cannot reroll while messages from the same conversation are processing.")
                        return
                    await self.reroll_messages(log, conversation_id, user_id)
                    break

    async def reroll_messages(self, conversation_log, conversation_id, user_id):
        channel = self.bot.get_channel(conversation_log["channel_id"])
        for message in reversed(conversation_log['messages']):
            for msg_id in message['message_ids']:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.delete()
                except Exception as e:
                    logger.error(f"Failed to delete message: {e}")
            conversation_log['messages'].remove(message)
            if message['role'] == 'assistant':  # Stop once the last LLM message is deleted
                break
        # Re-add the delete reaction to the new last message if exists
        if conversation_log['messages']:
            try:
                last_msg_id = conversation_log['messages'][-1]['message_ids'][-1]
                if last_msg_id:
                    last_msg = conversation_log['messages'][-1]
                    self.save_conversation_log(conversation_id)
                    await self.queue.put((conversation_id, last_msg, False))
            except Exception as e:
                logger.info(f"No message to add a reaction to: {e}")

    async def handle_delete_reaction(self, message_id, user_id):
        for conversation_id, log in self.conversation_logs.items():
            for msg in log['messages']:
                if user_id == log['user_id'] and message_id in msg.get('message_ids', []):
                    is_active = any(item[0] == conversation_id for item in self.queue._queue)
                    if is_active:
                        logger.info("Cannot delete messages while messages from the same conversation are processing.")
                        return
                    await self.delete_messages(log, conversation_id)
                    break

    async def delete_messages(self, conversation_log, conversation_id):
        channel = self.bot.get_channel(conversation_log["channel_id"])
        for message in reversed(conversation_log['messages']):
            for msg_id in message['message_ids']:
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.delete()
                except Exception as e:
                    logger.error(f"Failed to delete message: {e}")
            conversation_log['messages'].remove(message)
            if message['role'] == 'user':  # Stop once the last message is deleted
                break

        self.save_conversation_log(conversation_id)
        # Re-add the delete reaction to the new last message if exists
        if conversation_log['messages']:
            try:
                last_msg_id = conversation_log['messages'][-1]['message_ids'][-1]
                if last_msg_id:
                    last_msg = await channel.fetch_message(last_msg_id)
                    await last_msg.add_reaction('🔄')
                    await last_msg.add_reaction('🗑️')
            except Exception as e:
                logger.info(f"No message to add a reaction to: {e}")

    def clear_conversation_log(self, conversation_id, user_id):
        log_file = f"./logs/conversations/{conversation_id}.json"
        image_folder = f"./logs/conversations/img_{conversation_id}"
        
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    conversation_log = json.load(f)
                    if conversation_log["user_id"] == user_id:
                        if self.queue.qsize() == 0:
                            self.conversation_logs.pop(conversation_id, None)
                            f.close()
                            os.remove(log_file)
                            
                            # Delete the image folder if it exists
                            if os.path.exists(image_folder):
                                shutil.rmtree(image_folder)
                            
                            logger.info(f"Conversation log and image folder cleared for {conversation_id}.")
                            return "Conversation log and image folder cleared."
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
