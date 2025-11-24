from telethon import TelegramClient
from telethon.sessions import StringSession
from loguru import logger
from typing import Optional
import os

from .config import Config
from .storage import RedisStorage
from .handlers import ChatEventHandler, CommandHandler

class Bot:
    def __init__(self) -> None:
        """Initialize bot instance"""
        self.storage: RedisStorage = RedisStorage()

        existing_session = self.storage.get_bot_session()
        session = StringSession(existing_session) if existing_session else StringSession()

        self.client: TelegramClient = TelegramClient(
            session,
            Config.API_ID,
            Config.API_HASH
        ).start(bot_token=Config.BOT_TOKEN)

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
        
        # Initialize Start video
        try:
            if not self.storage.get_start_video():
                video_path = "media/Giveaway.mp4"
                if os.path.exists(video_path):
                    logger.info(f"Uploading {video_path} to Telegram servers...")
                    
                    # Get video attributes
                    from telethon.utils import get_attributes
                    attributes = get_attributes(video_path)
                    
                    uploaded = await self.client.upload_file(video_path)
                    
                    data = {
                        "id": uploaded.id,
                        "parts": uploaded.parts,
                        "name": uploaded.name,
                        "type": "input_file"
                    }
                    if hasattr(uploaded, 'md5_checksum'):
                        data['md5'] = uploaded.md5_checksum
                    
                    # Serialize attributes for storage
                    serialized_attributes = []
                    for attr in attributes:
                        if hasattr(attr, 'to_dict'):
                            serialized_attributes.append({'_': attr.__class__.__name__, **attr.to_dict()})
                        else:
                            # Fallback for simpler serialization if needed, or custom handling
                            pass
                            
                    # For now, we'll store basic metadata if needed, but telethon might need raw attributes.
                    # Actually, storing the InputFile is enough, we can re-create attributes or let telethon infer.
                    # But for video, it's good to have width/height/duration.
                    # Let's just save the file ID details for now.
                    
                    self.storage.save_start_video(data)
                    logger.info("Start video uploaded and ID saved to Redis")
                else:
                    logger.warning(f"{video_path} not found")
        except Exception as e:
            logger.error(f"Failed to initialize Start video: {str(e)}")
        
        logger.info("Bot handlers registered successfully")

    def run(self) -> None:
        """Run the bot"""
        logger.info("Starting bot...")
        
        with self.client:
            self.client.loop.run_until_complete(self.setup())
            self.client.run_until_disconnected() 