import os
import sys
import asyncio

import discord
from discord.ext import commands
from discord import app_commands
from loguru import logger
from dotenv import load_dotenv
from settings import handle_settings_command
from utils import load_config
from conversationQueue import ConversationQueue

load_dotenv()
bot_token = os.getenv('DISCORD_BOT_TOKEN')
config = load_config("config.json")

logger.add("./logs/bot_logs.log", rotation="50 MB")

class DiscordBot(discord.Client):
    '''The discord client class for the bot'''

    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.slash_command_tree = app_commands.CommandTree(self)
        self.settings_lock = asyncio.Lock()
        self.queue = ConversationQueue(self)

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return  # Ignore messages sent by the bot itself

        bot_mention = f'<@{self.user.id}>'
        if message.content.lower().startswith('hey llm') or bot_mention in message.content.lower() or message.reference and message.reference.resolved.author == self.user:
            content = message.content
            if content.lower().startswith('hey llm'):
                content = content[8:]  # Remove "hey llm " from the start of the message
            elif bot_mention in content.lower():
                content = content.replace(bot_mention, '', 1)  # Remove the bot's mention from the message
            await self.queue.add_conversation(message.channel.id, message.author.id, content, 'user')
            logger.info(f"Added message to queue: {content}")

    async def on_ready(self):
        """Log the bot's readiness state with user details"""
        ready_logger = logger.bind(user=self.user.name, userid=self.user.id)
        ready_logger.info("Login Successful")
        await self.slash_command_tree.sync()
        self.loop.create_task(self.queue.process_conversation())

    async def ensure_admin_channel(self, guild):
        """Ensure the llm-bot-admin channel exists with correct permissions"""
        for channel in guild.channels:
            if channel.name == 'llm-bot-admin' and isinstance(channel, discord.TextChannel):
                return channel
        
        # Create the channel if it does not exist
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        if config['require_admin_role']:
            overwrites[discord.utils.get(guild.roles, name='discord-llm-bot-admin')] = discord.PermissionOverwrite(read_messages=True)
        return await guild.create_text_channel('llm-bot-admin', overwrites=overwrites)

bot = DiscordBot(intents=discord.Intents.all())

@bot.slash_command_tree.command(name='clearllmconversation', description='Clear the conversation log of the current channel')
async def clear_conversation(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    user_id = interaction.user.id
    conversation_id = f"{channel_id}_{user_id}"
    
    message = bot.queue.clear_conversation_log(conversation_id, user_id)
    await interaction.response.send_message(message, ephemeral=True, delete_after=10)
    logger.info(f"Clear conversation attempt by user {user_id} in channel {channel_id}: {message}")


@bot.slash_command_tree.command(name='settings', description='Manage bot settings')
async def settings(interaction: discord.Interaction):
    if config['require_admin_role'] and not any(role.name == 'discord-llm-bot-admin' for role in interaction.user.roles):
        role_missing_bot_admin_msg = await interaction.response.send_message("You do not have the required role to use this command.", ephemeral=True, delete_after=10)
        return

    if not bot.settings_lock.locked():
        async with bot.settings_lock:
            logger.info(f"Settings command called by {interaction.user}")
            await interaction.response.defer()  # Defer the response to handle it in the admin channel
            admin_channel = await bot.ensure_admin_channel(interaction.guild)
            await handle_settings_command(interaction, logger, admin_channel)
    else:
        await interaction.response.send_message("Settings are currently being modified by another user. Please try again later.", ephemeral=True, delete_after=10)


async def quit_exit():
    '''Gracefully shuts down the bot and logs the shutdown'''
    # Perform cleanup tasks here if needed before exiting
    # Close resources, finish ongoing tasks, etc.
    logger.info("Shutting down.")
    await bot.close()
    sys.exit(0)

if __name__ == "__main__":
    try:
        bot.run(bot_token)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
