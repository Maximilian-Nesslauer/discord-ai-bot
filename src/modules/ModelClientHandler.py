import os
import requests
import time
from llama_cpp import Llama
from loguru import logger
from groq import Groq
from settings import load_settings
from utils import start_app, load_config

settings = load_settings("./src/settings/user_settings.json")
config = load_config("config.json")

class ModelClientManager():
    def __init__(self):
        self.clients = {}
        self.vram_usage = {}
        self.groq_client = GroqClient(api_key=os.getenv('GROQ_API_KEY'))
        self.ollama_client = OllamaClient(api_url=os.getenv('OLLAMA_API_URL'), app_path=os.getenv('OLLAMA_APP_PATH'))
        self.max_vram = config["max_vram_model_usage_GB"]

    def get_client(self, model_settings):
        if model_settings['api_type'] == "external_and_library":
            if model_settings['api'] == "groq":
                return self.groq_client
            
        elif model_settings['api_type'] == "local":
            required_vram = model_settings.get("vram_usage_gb", 0)

            if model_settings['api'] == "ollama":
                if self.check_vram_availability(required_vram):
                    self.vram_usage[model_settings['model_name']] = required_vram
                    return self.ollama_client
                else:
                    self.unload_unused_models()
                    if self.check_vram_availability(required_vram):
                        self.vram_usage[model_settings['model_name']] = required_vram
                        return self.ollama_client
                    else:
                        raise MemoryError(f"Insufficient VRAM to load {model_settings['model_name']}")
                    
            elif model_settings['api'] == "llama_cpp":
                llama_cpp_client = LlamaCppClient(
                    model_path=model_settings['model_path'],
                    chat_format=model_settings['chat_format']
                )
                return llama_cpp_client
            
        else:
            raise ValueError(f"Unsupported API type {model_settings['api_type']}")

    def make_llm_call(self, messages, model_settings, temperature, max_tokens, top_p, stream):
        client = self.get_client(model_settings)
        response = client.chat_completions(messages=messages, model=model_settings["model_name"], temperature=temperature, max_tokens=max_tokens, top_p=top_p, stream=stream)
        return response

    def check_vram_availability(self, required_vram):
        current_usage = sum(self.vram_usage.values())
        return current_usage + required_vram <= self.max_vram

    def update_vram_usage(self, bot, model_name, required_vram):
        if self.check_vram_availability(required_vram):
            self.unload_unused_models(bot)
            if self.check_vram_availability(required_vram):
                self.vram_usage[model_name] = required_vram
                return True
            else:
                return False
        else:
            return False

    def unload_model(self, model_name):
        """Unload the specified model by name."""
        if model_name in self.vram_usage:
            del self.vram_usage[model_name]

            if model_name in [key for key, value in settings['model_text']['choices'].items() if value['api'] == 'ollama']:
                self.ollama_client.unload_model(model_name)

            logger.info(f"Unloaded model {model_name} to free up VRAM.")

    def unload_unused_models(self, bot):
        active_models = self.get_active_model_names(bot)
        for model in list(self.vram_usage):
            if model not in active_models:
                self.unload_model(model)

    def get_active_model_names(self, bot):
        """Collect all active models used in conversations."""
        active_models = set()

        for conversation in bot.queue.conversation_logs.values():
            active_models.add(conversation["model_text"])
            active_models.add(conversation["model_img"])

        return active_models

class GroqClient():
    def __init__(self, api_key):
        self.client = Groq(api_key=api_key)

    def chat_completions(self, messages, model, temperature, max_tokens, top_p, stream):
        response = self.client.chat.completions.create(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream
        )
        return response.choices[0].message.content

class OllamaClient():
    def __init__(self, api_url, app_path):
        self.api_url = api_url
        self.app_path = app_path
        self.app_name = "ollama.exe"

    def chat_completions(self, messages, model, temperature, max_tokens, top_p, stream):
        start_app(self.app_path, self.app_name)
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_ctx": max_tokens,
                "top_p": top_p
            },
            "keep_alive": '10m'
        }
        response = requests.post(self.api_url + "/chat", json=payload)
        if response.status_code == 200:
            return response.json()['message']['content']
        elif response.status_code == 404:
            self.pull_model(model)
            time.sleep(10)
            return self.chat_completions(messages, model, temperature, max_tokens, top_p, stream)
        else:
            raise Exception(f"API call failed with status code {response.status_code}: {response.text}")

    def pull_model(self, model_name):
        """Pulls a model from the Ollama library"""
        logger.info(f"Pulling model '{model_name}' from Ollama library.")
        pull_response = requests.post(self.api_url + "/pull", json={"name": model_name})
        if pull_response.status_code == 200:
            logger.info(f"Model '{model_name}' pulled successfully.")
        else:
            logger.error(f"Failed to pull model '{model_name}': {pull_response.text}")

    def unload_model(self, model):
        """Unload a specific Ollama model by sending the appropriate API request."""
        payload = {
            "model": model,
            "keep_alive": '0'
        }

        response = requests.post(self.api_url + "/chat", json=payload)
        time.sleep(5)

class LlamaCppClient():
    def __init__(self, model_path, chat_format):
        self.client = Llama(model_path=model_path, chat_format=chat_format)

    def chat_completions(self, messages, model, temperature, max_tokens, top_p, stream):
        response = self.client.create_chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream
        )
        return response['choices'][0]['message']['content']
