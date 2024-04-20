import discord
import json

from utils import load_config

async def handle_settings_command(interaction, logger, admin_channel):
    config = load_config("config.json")
    settings = load_settings("./src/settings/user_settings.json")

    # Redirect interaction to the admin channel
    initial_msg = await admin_channel.send(f"{interaction.user.mention}, let's manage the settings here.")
    if config['delete_messages']:
        await initial_msg.delete(delay=20)

    # Manage settings with reactions for yes/no
    msg = await admin_channel.send("Do you want to load the default settings?")
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')

    def check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in ['✅', '❌']

    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=check)
    if str(reaction.emoji) == '✅':
        settings = load_settings("./src/settings/default_settings.json")
        default_settings_loaded_msg = await admin_channel.send("Default settings loaded.")
        if config['delete_messages']:
            await default_settings_loaded_msg.delete(delay=10)
    if config['delete_messages']:
        await msg.delete()

    # Handle value modifications based on type
    for key, setting in settings.items():
        if setting['type'] == 'choice':
            message_text = f"Choose a value for {key}: " + ' ; '.join([f"{k} ({v})" for k, v in setting['choices'].items()])
            msg = await admin_channel.send(message_text)
            for emoji in setting['choices'].values():
                await msg.add_reaction(emoji)

            def reaction_check(reaction, user):
                return user == interaction.user and str(reaction.emoji) in setting['choices'].values()

            reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=reaction_check)
            settings[key]['value'] = [k for k, v in setting['choices'].items() if v == str(reaction.emoji)][0]
            if config['delete_messages']:
                await msg.delete()

        elif setting['type'] == 'value':
            prompt_msg = await admin_channel.send(f"Please type a new numerical value for {key} in this channel:")
            def message_check(m):
                return m.author == interaction.user and m.channel == admin_channel and m.content.isdigit() # only accept numerical values to prevent injection attacks

            message = await interaction.client.wait_for('message', timeout=120.0, check=message_check)
            settings[key]['value'] = message.content
            if config['delete_messages']:
                await prompt_msg.delete()
                await message.delete()

    # Final confirmation for saving changes
    msg = await admin_channel.send("Do you want to save the changes?")
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')

    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=check)
    if config['delete_messages']:
        await msg.delete()
    if str(reaction.emoji) == '✅':
        save_settings_to_file(settings, "./src/settings/user_settings.json")
        save_msg = await admin_channel.send("Settings have been saved.")
        if config['delete_messages']:
            await save_msg.delete(delay=5)
    else:
        save_msg = await admin_channel.send("Changes not saved.")
        if config['delete_messages']:
            await save_msg.delete(delay=5)

    settings_update_complete_msg = await interaction.followup.send("Settings update complete.")
    await settings_update_complete_msg.delete(delay=5)

def load_settings(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # Return an empty dict if the file does not exist

def save_settings_to_file(settings, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)
