from telethon import TelegramClient
from telethon.sessions import StringSession
from loguru import logger
from typing import Optional

from .config import Config
from .storage import RedisStorage
from .handlers import ChatEventHandler, CommandHandler

class Bot:
    def __init__(self) -> None:
        """Initialize bot instance"""
        self.storage: RedisStorage = RedisStorage()

        # Load or create StringSession from Redis to avoid local SQLite
        existing_session = self.storage.get_bot_session()
        session = StringSession(existing_session) if existing_session else StringSession()

        self.client: TelegramClient = TelegramClient(
            session,
            Config.API_ID,
            Config.API_HASH
        ).start(bot_token=Config.BOT_TOKEN)

        # Persist session string if it was newly created
        if not existing_session:
            try:
                self.storage.save_bot_session(self.client.session.save())
                logger.info("Bot StringSession saved to Redis")
            except Exception as e:
                logger.error(f"Failed to save bot session: {str(e)}")
        self.chat_handler: Optional[ChatEventHandler] = None
        self.command_handler: Optional[CommandHandler] = None

    async def setup(self) -> None:
        """Setup bot handlers and initialize components"""
        self.chat_handler = ChatEventHandler(self)
        self.command_handler = CommandHandler(self)
        
        await self.chat_handler.register()
        await self.command_handler.register()
        
        logger.info("Bot handlers registered successfully")

    def run(self) -> None:
        """Run the bot"""
        logger.info("Starting bot...")
        
        with self.client:
            self.client.loop.run_until_complete(self.setup())
            self.client.run_until_disconnected() 