import os
from groq import Groq
from settings import load_settings

settings = load_settings("./src/settings/user_settings.json")

class ModelClientManager():
    def __init__(self):
        self.clients = {}
        self.groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

    def get_client(self, model_settings):
        if model_settings['api_type'] == "external_and_library":

            if model_settings['api'] == "groq":
                return self.groq_client
            
        else:
            raise ValueError(f"Unsupported API type {model_settings['api_type']}")

    
    def make_llm_call(self, messages, model_settings, temperature, max_tokens, top_p, stream):
        client = self.get_client(model_settings)
        response = client.chat.completions.create(
            messages=messages,
            model=model_settings["model_name"],
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stream=stream
        )
        return response
