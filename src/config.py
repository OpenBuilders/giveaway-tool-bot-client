import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_ID = int(os.getenv('API_ID', '7248451'))
    API_HASH = os.getenv('API_HASH', 'db9b16eff233ee8dfd7c218138cb2e10')
    BOT_TOKEN = os.getenv('BOT_TOKEN', '7944326047:AAHHD8lQ-weNEtylINDvxZTjLGUZ04VtN2c')
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    REDIS_DB = int(os.getenv('REDIS_DB', 0))
    
    # App configuration
    APP_URL = os.getenv('APP_URL', 'https://t.me/stage_give_bot?startapp') 