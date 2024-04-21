import os
import discord
import json

from loguru import logger

from utils import load_config

async def handle_settings_command(bot, interaction, logger):
    config = load_config("config.json")
    settings = load_settings("./src/settings/user_settings.json")

    channel = interaction.channel

    # load default settings if requested
    msg = await channel.send("Do you want to load the default settings?")
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')

    def check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in ['✅', '❌']

    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=check)
    if str(reaction.emoji) == '✅':
        settings = load_settings("./src/settings/default_settings.json")
        default_settings_loaded_msg = await channel.send("Default settings loaded.")
        if config['delete_messages']:
            await default_settings_loaded_msg.delete(delay=10)
    if config['delete_messages']:
        await msg.delete()

    # Handle model selection
    msg = await channel.send("Choose a value for {key}: " + ' ; '.join([f"{k} ({v})" for k, v in settings['model']['choices'].items()]))
    model_emojis = settings['model']['choices'].values()
    for emoji in model_emojis:
        await msg.add_reaction(emoji)

    def model_check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in model_emojis

    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=model_check)
    settings['model']['value'] = [k for k, v in settings['model']['choices'].items() if v == str(reaction.emoji)][0]
    if config['delete_messages']:
        await msg.delete()


    # Handle temperature setting
    await handle_numeric_setting(interaction, channel, settings, 'temperature', 0.1, 1.0, "Please type a new numerical value for temperature between 0.1 and 1.0:")

    # Handle max_tokens setting
    await handle_numeric_setting(interaction, channel, settings, 'max_tokens', 1, 4096, "Please type a new numerical value for max_tokens between 1 and 4096:")

    # Handle system prompt setting
    prompt_msg = await channel.send("Please type a new system prompt. The default is 'You are a highly skilled and helpful AI assistant.'")
    msg = await interaction.client.wait_for('message', timeout=120.0, check=lambda m: m.author == interaction.user and m.channel == channel)
    settings['system_prompt']['value'] = msg.content
    if config['delete_messages']:
        await msg.delete()
    
    # Final confirmation for saving changes
    msg = await channel.send("Do you want to save the changes?")
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')

    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=check)
    if config['delete_messages']:
        await msg.delete()
    if str(reaction.emoji) == '✅':
        save_settings_to_file(settings, "./src/settings/user_settings.json")
        save_msg = await channel.send("Settings have been saved.")
        update_conversation_log_with_settings(bot, interaction.channel_id, interaction.user.id, settings)
        if config['delete_messages']:
            await save_msg.delete(delay=5)
    else:
        save_msg = await channel.send("Changes not saved.")
        if config['delete_messages']:
            await save_msg.delete(delay=5)

    settings_update_complete_msg = await interaction.followup.send("Settings update complete.")
    await settings_update_complete_msg.delete(delay=5)

async def handle_numeric_setting(interaction, admin_channel, settings, key, min_value, max_value, prompt_message):
    config = load_config("config.json")
    prompt_msg = await admin_channel.send(prompt_message)
    valid_input = False

    while not valid_input:
        def message_check(m):
            return m.author == interaction.user and m.channel == admin_channel

        message = await interaction.client.wait_for('message', timeout=120.0, check=message_check)
        try:
            value = float(message.content)
            if min_value <= value <= max_value:
                if key == 'temperature':
                    settings[key]['value'] = float(value)
                elif key == 'max_tokens':
                    settings[key]['value'] = int(value)

                valid_input = True
                if config['delete_messages']:
                    await prompt_msg.delete()
                    await message.delete()
            else:
                invalid_input_msg = await admin_channel.send("Invalid input. Please enter a numerical value.")
                if config['delete_messages']:
                    await message.delete()
                    await invalid_input_msg.delete(delay=10)
        except ValueError:
            invalid_input_msg = await admin_channel.send("Invalid input. Please enter a numerical value.")
            if config['delete_messages']:
                await message.delete()
                await invalid_input_msg.delete(delay=10)


def load_settings(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}  # Return an empty dict if the file does not exist

def save_settings_to_file(settings, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)


def update_conversation_log_with_settings(bot, channel_id, user_id, settings):
    conversation_id = f"{channel_id}_{user_id}"
    log_file = f"./logs/conversations/{conversation_id}.json"

    # Update the conversation log in memory
    if conversation_id in bot.queue.conversation_logs:
        conversation_log = bot.queue.conversation_logs[conversation_id]
        conversation_log['model'] = settings['model']['value']
        conversation_log['temperature'] = settings['temperature']['value']
        conversation_log['max_tokens'] = settings['max_tokens']['value']
        conversation_log['system_prompt'] = settings['system_prompt']['value']
        bot.queue.save_conversation_log(conversation_id)

    # Update the conversation log in the file system
    if os.path.exists(log_file):
        with open(log_file, "r+") as f:
            conversation_log = json.load(f)
            conversation_log['model'] = settings['model']['value']
            conversation_log['temperature'] = settings['temperature']['value']
            conversation_log['max_tokens'] = settings['max_tokens']['value']
            conversation_log['system_prompt'] = settings['system_prompt']['value']
            conversation_log['messages'][0]['content'] = settings['system_prompt']['value']
            f.seek(0)
            json.dump(conversation_log, f, indent=4)
            f.truncate()




# maybe useful in handle_settings_command

    '''
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

            valid_input = False
            while not valid_input:
                def message_check(m):
                    # check if the correct user is responding in the correct channel
                    return m.author == interaction.user and m.channel == admin_channel

                message = await interaction.client.wait_for('message', timeout=120.0, check=message_check)
                if message.content.isdigit():
                    settings[key]['value'] = message.content
                    valid_input = True
                    if config['delete_messages']:
                        await prompt_msg.delete()
                        await message.delete()
                else:
                    invalid_input_msg = await admin_channel.send("Invalid input. Please enter a numerical value.")
                    if config['delete_messages']:
                        await message.delete()
                        await invalid_input_msg.delete(delay=10)
    '''