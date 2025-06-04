from loguru import logger
from src.bot import Bot

if __name__ == "__main__":
    try:
        # Configure logger
        logger.add(
            "logs/bot.log",
            rotation="1 day",
            retention="7 days",
            level="INFO"
        )
        
        # Start bot
        bot = Bot()
        bot.run()
    except Exception as e:
        logger.exception(f"Bot crashed: {str(e)}") 