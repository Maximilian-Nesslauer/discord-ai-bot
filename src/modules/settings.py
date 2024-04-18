import discord
import json

async def handle_settings_command(interaction, logger):
    settings = load_settings("user_settings.json")
    
    # Initial prompt for loading defaults
    await interaction.response.send_message("Do you want to load the default settings? (✅/❌)")
    msg = await interaction.original_response()
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')

    def check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in ['✅', '❌']

    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=check)
    if str(reaction.emoji) == '✅':
        settings = load_settings("default_settings.json")
        await interaction.followup.send("Default settings loaded.")
    
    # Modify settings
    for key, setting in settings.items():
        if setting['type'] == 'choice':
            message_text = f"Choose a value for {key}: " + ' '.join([f"{k} {v}" for k, v in setting['choices'].items()])
            msg = await interaction.followup.send(message_text)
            for emoji in setting['choices'].values():
                await msg.add_reaction(emoji)

            def reaction_check(reaction, user):
                return user == interaction.user and str(reaction.emoji) in setting['choices'].values()

            reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=reaction_check)
            settings[key]['value'] = [k for k, v in setting['choices'].items() if v == str(reaction.emoji)][0]
            await msg.delete()
        else:
            await interaction.followup.send(f"Please type a new value for {key} in this channel:")
            def message_check(m):
                return m.author == interaction.user and m.channel == interaction.channel

            message = await interaction.client.wait_for('message', timeout=120.0, check=message_check)
            settings[key]['value'] = message.content

    # Final prompt for saving
    msg = await interaction.followup.send("Do you want to save the changes? (✅/❌)")
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')
    
    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=check)
    if str(reaction.emoji) == '✅':
        save_settings_to_file(settings, "user_settings.json")
        await interaction.followup.send("Settings have been saved.")
    else:
        await interaction.followup.send("Changes not saved.")

def load_settings(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # Return an empty dict if the file does not exist

def save_settings_to_file(settings, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)
