import discord
import json

async def handle_settings_command(ctx, logger):
    settings = load_settings("user_settings.json")
    
    # Initial prompt for loading defaults
    msg = await ctx.send("Do you want to load the default settings? (✅/❌)")
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')

    def check(reaction, user):
        return user == ctx.author and reaction.message.id == msg.id and str(reaction.emoji) in ['✅', '❌']

    reaction, _ = await ctx.bot.wait_for('reaction_add', check=check)
    await msg.delete()
    if str(reaction.emoji) == '✅':
        settings = load_settings("default_settings.json")
        confirm_msg = await ctx.send("Default settings loaded.")
        await confirm_msg.delete(delay=5)
    
    # Modify settings
    for key, setting in settings.items():
        if setting['type'] == 'choice':
            message_text = f"Choose a value for {key}: " + ' '.join([f"{k} {v}" for k, v in setting['choices'].items()])
            message = await ctx.send(message_text)
            for emoji in setting['choices'].values():
                await message.add_reaction(emoji)

            def reaction_check(reaction, user):
                return user == ctx.author and reaction.message.id == message.id and str(reaction.emoji) in setting['choices'].values()

            reaction, _ = await ctx.bot.wait_for('reaction_add', check=reaction_check)
            settings[key]['value'] = [k for k, v in setting['choices'].items() if v == str(reaction.emoji)][0]
            await message.delete()
        else:
            prompt_msg = await ctx.send(f"Please type a new value for {key}:")
            def message_check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            message = await ctx.bot.wait_for('message', check=message_check)
            settings[key]['value'] = message.content
            await prompt_msg.delete()
            await message.delete()

    # Final prompt for saving
    msg = await ctx.send("Do you want to save the changes? (✅/❌)")
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')
    
    reaction, _ = await ctx.bot.wait_for('reaction_add', check=check)
    if str(reaction.emoji) == '✅':
        save_settings_to_file(settings, "user_settings.json")
        save_confirm_msg = await ctx.send("Settings have been saved.")
    else:
        save_confirm_msg = await ctx.send("Changes not saved.")
    await msg.delete()
    await save_confirm_msg.delete(delay=5)

def load_settings(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_settings_to_file(settings, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)
