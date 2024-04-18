import discord
from discord.ext import commands
from loguru import logger
from dotenv import load_dotenv
import os
from settings import handle_settings_command

load_dotenv() 
bot_token = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
intents.guilds = True

logger.add("./logs/bot_logs.log", rotation="50 MB")

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}!')

@bot.command()
@commands.has_role('discord-llm-bot-admin')
async def settings(ctx):
    logger.info(f"Settings command called by {ctx.author}")
    await handle_settings_command(ctx, logger)

if __name__ == "__main__":
    try:
        bot.run(bot_token)
    except Exception as e:
        logger.error(f"Error running bot: {e}")
