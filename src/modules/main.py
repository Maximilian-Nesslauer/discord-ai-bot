import os
import sys
import asyncio
import discord
from datetime import datetime
from discord.ext import commands
from discord import app_commands
from loguru import logger
from dotenv import load_dotenv
from settings import handle_settings_command, handle_characters_command
from utils import load_config, start_app
from requestQueue import RequestQueue

# Load environment variables from .env file
load_dotenv()
bot_token = os.getenv('DISCORD_BOT_TOKEN')
config = load_config("config.json")
rate_limit_per_user_per_minute = config['rate_limit_per_user_per_minute']
ollama_app_path = os.getenv('OLLAMA_APP_PATH')

logger.add("./logs/bot_logs.log", rotation="50 MB")

class DiscordBot(discord.Client):
    '''The discord client class for the bot'''

    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        self.slash_command_tree = app_commands.CommandTree(self)
        self.queue = RequestQueue(self)
        self.users_in_settings = set()
        self.user_message_timestamps = {}

        try:
            start_app(ollama_app_path, "ollama.exe")
        except Exception as e:
            logger.error(f"Failed to start app on DiscordBot __init__: {e}")

    async def on_message(self, message: discord.Message):
        # Ignore messages from the bot itself or while user is in settings
        if message.author == self.user or message.author.id in self.users_in_settings:
            return
        
        # Rate limit check
        user_id = message.author.id
        current_time = datetime.now().timestamp()
        if user_id not in self.user_message_timestamps:
            self.user_message_timestamps[user_id] = []
        
        # Filter out timestamps older than 1 minute
        self.user_message_timestamps[user_id] = [timestamp for timestamp in self.user_message_timestamps[user_id] if current_time - timestamp < 60]
        
        if len(self.user_message_timestamps[user_id]) >= rate_limit_per_user_per_minute:
            await message.channel.send(f"{message.author.mention}, you are sending messages too quickly. Please slow down.", delete_after=5)
            return
        
        # Add the current timestamp to the user's message timestamps
        self.user_message_timestamps[user_id].append(current_time)

        bot_mention = f'<@{self.user.id}>'
        if (message.channel.name == f'llm-{message.author.name}' or
                message.content.lower().startswith('hey llm') or
                bot_mention in message.content.lower() or
                (message.reference and message.reference.resolved and message.reference.resolved.author == self.user)):
            content = message.content
            if content.lower().startswith('hey llm'):
                content = content[8:]  # Remove "hey llm " from the start of the message
            elif bot_mention in content.lower():
                content = content.replace(bot_mention, '', 1)  # Remove the bot's mention from the message
            await self.queue.add_conversation(message.channel.id, message.author.id, content, 'user', message.id, create_empty=False)
            logger.info(f"Added message to queue: {content}")

    async def on_ready(self):
        """Logs the bot's readiness state with user details and starts processing the conversation queue."""
        ready_logger = logger.bind(user=self.user.name, userid=self.user.id)
        ready_logger.info("Login Successful")
        await self.slash_command_tree.sync()
        self.loop.create_task(self.queue.process_conversation())

    async def ensure_admin_channel(self, guild):
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
bot.queue.load_conversation_logs()

@bot.event
async def on_reaction_add(reaction, user):
    try:
        if user == bot.user:
            return
        
        if reaction.emoji == "🔄":
            await bot.queue.handle_reroll_reaction(reaction.message.id, user.id)
        if reaction.emoji == '🗑️':
            await bot.queue.handle_delete_reaction(reaction.message.id, user.id)
    except Exception as e:
        logger.error(f"Failed to handle reaction: {e}")

@bot.slash_command_tree.command(name='setupllm', description='Print a welcome message to set up the LLM bot for users')
async def setup_llm(interaction: discord.Interaction):
    channel = interaction.channel

    await interaction.response.defer()

    msg = await interaction.followup.send("Sending welcome message.")
    await msg.delete(delay=1)

    welcome_message = (
        "**Welcome to the LLM Bot!** 🎉\n\n"
        "Here's how you can interact with the bot:\n\n"
        "- **Start a new conversation:** Use the command `/newllmconversation`.\n"
        "- **Chat with the bot:** Mention the bot or start your message with 'hey llm'. There is no need for the 'hey llm' trigger if you are in your private llm channel.\n"
        "- **Adjust settings:** Use the `/settings` command to specify which model to use and to modify conversation parameters.\n"
        "- **Assign the bot different Characters:** Use the `/characters` command to specify which characters to use.\n"
        "- **Clear history:** Use `/clearllmconversation` to delete the conversation history in this channel. Regular maintenance ensures optimal performance.\n\n"
        "Enjoy your conversations with the LLM bot!"
    )
    await channel.send(welcome_message)

@bot.slash_command_tree.command(name='newllmconversation', description='Start a new LLM conversation channel')
async def new_llm_conversation(interaction: discord.Interaction):
    guild = interaction.guild
    user = interaction.user
    
    # Create a new private channel with the user's name
    channel_name = f'llm-{user.name}'
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True),
        user: discord.PermissionOverwrite(read_messages=True)
    }

    existing_channel = discord.utils.get(guild.channels, name=channel_name, type=discord.ChannelType.text)
    if not existing_channel:
        new_channel = await guild.create_text_channel(channel_name, overwrites=overwrites)
        await interaction.response.defer()

        msg = await interaction.followup.send(f"Created new channel: <#{new_channel.id}>.")
        await msg.delete(delay=10)

        # Send a message in the new channel
        await new_channel.send(f"Hey {user.mention}, let's start our conversation here.")
        await bot.queue.add_conversation(new_channel.id, user.id, "null", 'user', create_empty=True)
    else:
        await interaction.response.send_message(f"Conversation channel already exists for {user.mention}.", ephemeral=True, delete_after=5)

@bot.slash_command_tree.command(name='deletellmconversation', description='Delete and Clear the conversation log of the current channel')
async def clear_conversation(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    user_id = interaction.user.id
    conversation_id = f"{channel_id}_{user_id}"
    
    message = bot.queue.clear_conversation_log(conversation_id, user_id)
    await interaction.response.send_message(message, ephemeral=True, delete_after=10)

    channel = interaction.channel
    user_name = interaction.user.name
    if user_name.lower() in channel.name.lower():
        await channel.delete()
    logger.info(f"Delete and Clear conversation attempt by user {user_id} in channel {channel_id}: {message}")

@bot.slash_command_tree.command(name='clearllmconversation', description='Clear the conversation log of the current channel')
async def clear_conversation(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    user_id = interaction.user.id
    conversation_id = f"{channel_id}_{user_id}"
    
    message = bot.queue.clear_conversation_log(conversation_id, user_id)
    await interaction.response.send_message(message)

    logger.info(f"Clear conversation attempt by user {user_id} in channel {channel_id}: {message}")

@bot.slash_command_tree.command(name='settings', description='Manage bot settings')
async def settings(interaction: discord.Interaction):
    bot.users_in_settings.add(interaction.user.id)
    
    try:
        # Ensure there's an ongoing conversation in the channel
        conversation_id = f"{interaction.channel_id}_{interaction.user.id}"
        if conversation_id not in bot.queue.conversation_logs:
            await interaction.response.send_message("No active conversation found in this channel.", ephemeral=True, delete_after=10)
            bot.users_in_settings.remove(interaction.user.id)
            return
        
        logger.info(f"Settings command called by {interaction.user}")
        await interaction.response.defer()
        await handle_settings_command(bot, interaction, logger)
        bot.users_in_settings.remove(interaction.user.id)

    except Exception as e:
        logger.error(f"Error in settings command: {e}")
        bot.users_in_settings.remove(interaction.user.id)

@bot.slash_command_tree.command(name='characters', description='Manage bot character')
async def characters(interaction: discord.Interaction):
    bot.users_in_settings.add(interaction.user.id)
    
    try:
        # Ensure there's an ongoing conversation in the channel
        conversation_id = f"{interaction.channel_id}_{interaction.user.id}"
        if conversation_id not in bot.queue.conversation_logs:
            await interaction.response.send_message("No active conversation found in this channel.", ephemeral=True, delete_after=10)
            bot.users_in_settings.remove(interaction.user.id)
            return
        
        logger.info(f"Characters command called by {interaction.user}")
        await interaction.response.defer()
        await handle_characters_command(bot, interaction, logger)
        bot.users_in_settings.remove(interaction.user.id)

    except Exception as e:
        logger.error(f"Error in characters command: {e}")
        bot.users_in_settings.remove(interaction.user.id)

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
