import json
import psutil
import subprocess
import time
from loguru import logger

def load_config(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    
def is_app_running(app_name):
    for process in psutil.process_iter(['name']):
        if process.info['name'] == app_name:
            logger.info(f"Application '{app_name}' is currently running.")
            return True
    logger.info(f"Application '{app_name}' is not running.")
    return False

def start_app(app_path, app_name):
    """Start an application if it is not already running"""
    if not is_app_running(app_name):
        logger.info(f"Starting application '{app_name}' from path '{app_path}'.")
        subprocess.Popen(app_path, shell=True)
        time.sleep(5)  # Wait for the application to fully initialize
        logger.info(f"Application '{app_name}' should now be running.")