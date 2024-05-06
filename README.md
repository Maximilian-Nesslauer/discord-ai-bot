# discord-ai-bot

A Discord bot that uses a Large Language Model (LLM) to chat with users.

## Overview

This project aims to create a Discord bot that enables users to chat with an LLM.

The bot can either connect to APIs like

- oobabooga's text-generation-webui (<https://github.com/oobabooga/text-generation-webui>)
- groq (<https://groq.com/>)
- OpenAI's GPT-4 API (<https://openai.com/product>)
- any other OpenAI API style API

or locally host an LLM with the transformers and llama cpp libraries (WIP).

Future Enhancements will include image generation capabilities through Stable Diffusion models and Voice Conversations in Discord Channels through localy hosted open source speech recognition and generation models.

The goal of the project is to gain more coding experience and just having fun with the bot.

## Features

### Chat Interaction

- **AI Conversations**: Users can engage in conversations with the AI directly in Discord using slash commands or direct mentions. The user can create an own private channel with the '/newllmconversation' command to have a private conversation.
- **AI Characters**: The user can use the '/characters' command to choose between different Characters. Different System prompts and messages will be injected into the conversation depending on the Character.

### Resource Management

- **Dynamic Loading/Unloading**: To efficiently manage system resources like VRAM/RAM, the bot can dynamically load and unload models based on the current task, ensuring optimal performance even on limited hardware. If we want to add an image generation model for example and if There is not enough VRAM available the queue should (toggle in settings) unload the LLM model -> load the Image model and generate the image -> unload the Image model and load the LLM model again. Keeping everything in VRAM instead of letting it spill over into RAM will lead to loading times between LLM -> Image Model -> LLM switches but make the LLMs much faster.
- **Queue System**: A queue system manages requests to the AI, maintaining order and prioritizing tasks as needed, ensuring that every user interaction is handled smoothly.

## How to use

- go to <https://discord.com/developers/applications> and get a token for your bot with sufficient permissions -> save your token to .env . Never share this token!
- If you want to use Ollama: Install Ollama and change the Ollama exe Path in .env

- For Windows Users

    ```bash
    # Activate your virtual environment
    .\.venv\Scripts\activate

    # Install required Python packages
    pip install -r requirements.txt
    ```

## Feedback is always welcome! :)

## TODO

- Image Generation
- Voice Conversations
