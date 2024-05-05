import os
import requests
import time
from loguru import logger
from groq import Groq
from settings import load_settings
from utils import start_app

settings = load_settings("./src/settings/user_settings.json")

class ModelClientManager():
    def __init__(self):
        self.clients = {}
        self.groq_client = GroqClient(api_key=os.getenv('GROQ_API_KEY'))
        self.ollama_client = OllamaClient(api_url=os.getenv('OLLAMA_API_URL'), app_path=os.getenv('OLLAMA_APP_PATH'))

    def get_client(self, model_settings):
        if model_settings['api_type'] == "external_and_library":

            if model_settings['api'] == "groq":
                return self.groq_client
            
        elif model_settings['api_type'] == "local":
            if model_settings['api'] == "ollama":
                return self.ollama_client
            
        else:
            raise ValueError(f"Unsupported API type {model_settings['api_type']}")

    def make_llm_call(self, messages, model_settings, temperature, max_tokens, top_p, stream):
        client = self.get_client(model_settings)
        response = client.chat_completions(messages=messages, model=model_settings["model_name"], temperature=temperature, max_tokens=max_tokens, top_p=top_p, stream=stream)
        return response
    
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


    