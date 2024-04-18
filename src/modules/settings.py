import discord
import json
from discord.utils import get

async def handle_settings_command(ctx, logger):
    settings = load_settings("user_settings.json")
    
    # Initial prompt for loading defaults
    def check(reaction, user):
        return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ['✅', '❌']
    
    msg = await ctx.send("Do you want to load the default settings? (✅/❌)")
    for emoji in ['✅', '❌']:
        await msg.add_reaction(emoji)

    reaction, _ = await ctx.bot.wait_for('reaction_add', check=check)
    if str(reaction.emoji) == '✅':
        settings = load_settings("default_settings.json")
        await ctx.send("Default settings loaded.")
    
    # Modify settings
    for key, setting in settings.items():
        await ctx.send(f"Setting: {key}, Current Value: {setting['value']}")
        if setting['type'] == 'choice':
            message = await ctx.send(f"Choose a value for {key}: {' '.join(setting['choices'])}")
            for choice in setting['choices']:
                await message.add_reaction(emoji_choice(choice))
            reaction, _ = await ctx.bot.wait_for('reaction_add', check=lambda r, u: r.message.id == message.id and str(r.emoji) in setting['choices'])
            settings[key]['value'] = str(reaction.emoji)
        else:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel
            await ctx.send(f"Please type a new value for {key}:")
            message = await ctx.bot.wait_for('message', check=check)
            settings[key]['value'] = message.content

    # Final prompt for saving
    msg = await ctx.send("Do you want to save the changes to user_settings.json? If yes Settings will persist across sessions. (✅/❌)")
    for emoji in ['✅', '❌']:
        await msg.add_reaction(emoji)
    
    reaction, _ = await ctx.bot.wait_for('reaction_add', check=check)
    if str(reaction.emoji) == '✅':
        save_settings_to_file(settings, "user_settings.json")
        await ctx.send("Settings have been saved.")
    else:
        await ctx.send("Changes not saved.")

def load_settings(filename):
    with open(filename, 'r') as f:
        return json.load(f)

def save_settings_to_file(settings, filename):
    with open(filename, 'w') as f:
        json.dump(settings, f, indent=4)

def emoji_choice(choice):
    return {
        "A": "🅰", "B": "🅱", "C": "C",
        "Yes": "✅", "No": "❌"
    }.get(choice, choice)
