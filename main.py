from loguru import logger
from src.bot import Bot
import sys

if __name__ == "__main__":
    try:
        # Configure logger to stdout
        logger.remove()
        logger.add(sys.stdout, level="INFO")
        
        # Start bot
        bot = Bot()
        bot.run()
    except Exception as e:
        logger.exception(f"Bot crashed: {str(e)}") 