from loguru import logger
from src.bot import Bot
import sys
from src.health import start_health_server
from src.config import Config

if __name__ == "__main__":
    try:
        # Configure logger to stdout
        logger.remove()
        logger.add(sys.stdout, level="INFO")
        
        # Start health server
        start_health_server(Config.HEALTH_PORT)

        # Start bot
        bot = Bot()
        bot.run()
    except Exception as e:
        logger.exception(f"Bot crashed: {str(e)}") 