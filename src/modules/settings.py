import os
import discord
import json
from loguru import logger
from utils import load_config

config = load_config("config.json")

async def handle_settings_command(bot, interaction, logger):
    settings = load_settings("./src/settings/user_settings.json")
    model_client_manager = bot.queue.model_client_manager

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

    await handle_model_selection(bot, interaction, model_client_manager, settings, 'model_text', "text")
    await handle_model_selection(bot, interaction, model_client_manager, settings, 'model_img', "image")

    # Handle temperature setting
    await handle_numeric_setting(interaction, channel, settings, 'temperature', 0.1, 1.0, "Please type a new numerical value for temperature between 0.1 and 1.0:")

    # Handle max_tokens setting
    await handle_numeric_setting(interaction, channel, settings, 'max_tokens', 1, 8192, "Please type a new numerical value for max_tokens between 1 and 8192:")

    # Handle system prompt setting
    prompt_msg = await channel.send("Please type a new system prompt. The default is 'You are a highly skilled and helpful AI assistant.'")
    msg = await interaction.client.wait_for('message', timeout=120.0, check=lambda m: m.author == interaction.user and m.channel == channel)
    settings['characters']['Assistant']['system_prompt'] = msg.content
    if config['delete_messages']:
        await prompt_msg.delete()
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

async def handle_model_selection(bot, interaction, model_client_manager, settings, setting_key, model_type):
    channel = interaction.channel
    model_prompt = f"Choose a {model_type} model:\n\n" + '\n\n'.join([f"\u2002\u2002{choice['emoji']} {name}" for name, choice in settings[setting_key]['choices'].items()]) + '\n\u200B'
    msg = await channel.send(model_prompt)
    model_emojis = [choice['emoji'] for choice in settings[setting_key]['choices'].values()]
    for emoji in model_emojis:
        await msg.add_reaction(emoji)

    def model_check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in model_emojis

    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=model_check)
    selected_model_key = next(key for key, value in settings[setting_key]['choices'].items() if value['emoji'] == str(reaction.emoji))
    selected_model_settings = settings[setting_key]['choices'][selected_model_key]

    if selected_model_settings['api_type'] == "local":
        required_vram = selected_model_settings.get("vram_usage_gb", 0)
        # Check VRAM before applying settings
        if not model_client_manager.check_vram_availability(selected_model_settings.get("vram_usage_gb", 0)):
            await channel.send("Insufficient VRAM to load this model. Please choose another model or unload models by deleting active conversations using these models.")
            return await handle_model_selection(bot, interaction, model_client_manager, settings, setting_key, model_type)
        
        model_client_manager.update_vram_usage(bot, selected_model_key, required_vram)


    settings[setting_key]['value'] = selected_model_key
    if config['delete_messages']:
        await msg.delete()

async def handle_characters_command(bot, interaction, logger):
    config = load_config("config.json")
    settings = load_settings("./src/settings/user_settings.json")

    channel = interaction.channel

    def check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in ['✅', '❌']

    # Handle text model selection
    character_prompt = "Choose a character:\n\n" + '\n\n'.join([f"\u2002\u2002{choice['emoji']} {name} - {choice['description']}" for name, choice in settings['characters'].items()]) + '\n\u200B'
    msg = await channel.send(character_prompt)
    character_emojis = [choice['emoji'] for choice in settings['characters'].values()]
    for emoji in character_emojis:
        await msg.add_reaction(emoji)

    def character_check(reaction, user):
        return user == interaction.user and str(reaction.emoji) in character_emojis

    reaction, _ = await interaction.client.wait_for('reaction_add', timeout=60.0, check=character_check)
    selected_character_key = next(key for key, value in settings['characters'].items() if value['emoji'] == str(reaction.emoji))
    if config['delete_messages']:
        await msg.delete()

    await update_conversation_with_character(bot, interaction.channel_id, interaction.user.id, selected_character_key, settings['characters'][selected_character_key], logger)

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

def update_conversation_log_with_settings(bot, channel_id, user_id, settings):
    conversation_id = f"{channel_id}_{user_id}"
    log_file = f"./logs/conversations/{conversation_id}.json"

    # Update the conversation log in memory
    if conversation_id in bot.queue.conversation_logs:
        conversation_log = bot.queue.conversation_logs[conversation_id]
        conversation_log['model_text'] = settings['model_text']['value']
        conversation_log['model_img'] = settings['model_img']['value']
        conversation_log['temperature'] = settings['temperature']['value']
        conversation_log['max_tokens'] = settings['max_tokens']['value']
        conversation_log['character'] = settings['character_value']
        if conversation_log['character'] == 'Assistant':
            conversation_log['assistant_system_prompt'] = settings['characters']['Assistant']['system_prompt']
        bot.queue.save_conversation_log(conversation_id)

    # Update the conversation log in the file system
    if os.path.exists(log_file):
        with open(log_file, "r+") as f:
            conversation_log = json.load(f)
            conversation_log['model_text'] = settings['model_text']['value']
            conversation_log['model_img'] = settings['model_img']['value']
            conversation_log['temperature'] = settings['temperature']['value']
            conversation_log['max_tokens'] = settings['max_tokens']['value']
            conversation_log['character'] = settings['character_value']
            if conversation_log['character'] == 'Assistant':
                conversation_log['assistant_system_prompt'] = settings['characters']['Assistant']['system_prompt']
                conversation_log['messages'][0]['content'] = settings['characters']['Assistant']['system_prompt']
            f.seek(0)
            json.dump(conversation_log, f, indent=4)
            f.truncate()

async def update_conversation_with_character(bot, channel_id, user_id, character_key, character, logger):
    conversation_id = f"{channel_id}_{user_id}"
    if conversation_id not in bot.queue.conversation_logs:
        logger.error(f"No conversation log found for {conversation_id}")
        return

    conversation_log = bot.queue.conversation_logs[conversation_id]

    conversation_log['character'] = character_key
    
    non_character_msgs = [msg for msg in conversation_log['messages'] if msg.get('type') != 'character_msg']
    
    new_character_msgs = [{
        "role": "system",
        "content": character['system_prompt'],
        "type": "character_msg"
    }]
    
    character_messages = character.get('messages', [])
    for msg in character_messages:
        msg['type'] = 'character_msg'
        new_character_msgs.append(msg)
    conversation_log['messages'] = new_character_msgs + non_character_msgs
    bot.queue.save_conversation_log(conversation_id)



def load_settings(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_settings_to_file(settings, filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=4)