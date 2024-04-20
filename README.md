# discord-ai-bot

Discord Bot that uses a LLM to chat with users

## Overview

This project aims to create a Discord bot that enables users to chat with an LLM.

The bot will initially connect to external APIs like oobabooga's text-generation-webui (<https://github.com/oobabooga/text-generation-webui>), groq (<https://groq.com/>), OpenAI's gpt-4 API (<https://openai.com/product>) or any other OpenAI API style API.

Future Enhancements will include local model hosting and integrating image generation capabilities.

(I am aware that repos with similar functionalities might already exist. The goal of the project however is to expand my coding skills and having control over my own project.)

## Features

### Chat Interaction

- **AI Conversations**: Users can engage in conversations with the AI directly through Discord using slash commands or direct mentions.
- **Dynamic Responses**: The bot utilizes LLMs to generate contextually relevant and engaging responses.

### Resource Management

- **Dynamic Loading/Unloading**: To efficiently manage system resources like VRAM/RAM, the bot can dynamically load and unload models based on the current task, ensuring optimal performance even on limited hardware. If we want to add an image generation model for example and if There is not enough VRAM available the queue should (toggle in settings) unload the LLM model -> load the Image model and generate the image -> unload the Image model and load the LLM model again. Keeping everything in VRAM instead of letting it spill over into RAM will lead to loading times between LLM -> Image Model -> LLM switches but make the LLMs much faster.
- **Queue System**: A queue system manages requests to the AI, maintaining order and prioritizing tasks as needed, ensuring that every user interaction is handled smoothly.

## How to use

- go to <https://discord.com/developers/applications> and get a token for your bot with sufficient permissions -> save your token to .env . Never share this token!

## TODO

## For Windows Developers

.\.venv\Scripts\activate

pip install -r -\requirements.txt

pip freeze > .\requirements.txt
