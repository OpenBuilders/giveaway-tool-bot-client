from typing import TYPE_CHECKING
from telethon import events, TelegramClient
from telethon.tl.types import User, Channel
from loguru import logger
import aiohttp
import io

if TYPE_CHECKING:
    from ..bot import Bot

from ..config import Config

class ChatEventHandler:
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.client = bot.client
        self.storage = bot.storage

    async def register(self) -> None:
        """Register all chat event handlers"""
        self.client.add_event_handler(
            self._handle_chat_action,
            events.ChatAction
        )

    def _normalize_channel_id(self, channel_id: int) -> int:
        """Convert any channel ID format to -100 prefix format"""
        str_id = str(channel_id)
        if not str_id.startswith('-100'):
            return int(f'-100{str_id}')
        return channel_id

    async def _handle_chat_action(self, event: events.ChatAction.Event) -> None:
        """Handle bot being added to or removed from a chat"""
        try:
            me = await self.client.get_me()

            if event.user_added:
                await self._handle_bot_added(event, me)
            elif event.user_kicked:
                await self._handle_bot_kicked(event, me)

        except Exception as e:
            logger.error(f"Error in chat action handler: {str(e)}")

    async def _handle_bot_added(self, event: events.ChatAction.Event, me: User) -> None:
        """Handle bot being added to a channel"""
        try:
            if not event.action_message:
                new_participant = event.original_update.new_participant
                if new_participant and new_participant.user_id == me.id:
                    chat: Channel = await event.get_chat()
                    chat_id = self._normalize_channel_id(chat.id)
                    user_id = event.added_by.id
                    
                    # Получаем и сохраняем аватарку канала
                    await self._save_channel_avatar(chat)
                    
                    self.storage.add_channel_for_user(user_id, chat_id)
                    logger.info(f"Bot was added to channel {chat_id} by user {user_id}")

        except Exception as e:
            logger.error(f"Error handling bot addition: {str(e)}")

    async def _save_channel_avatar(self, chat: Channel) -> None:
        """Save channel avatar to CDN and store URL in Redis"""
        try:
            # Получаем фотографии профиля канала
            photos = await self.client.get_profile_photos(chat)
            
            if photos:
                # Берем первую (самую последнюю) фотографию
                photo = photos[0]
                
                # Получаем данные фотографии в памяти
                photo_data = await self.client.download_media(photo, bytes)
                
                if photo_data:
                    # Загружаем в CDN
                    cdn_url = await self._upload_to_cdn(photo_data, f"channel_{chat.id}_avatar.jpg")
                    
                    if cdn_url:
                        # Сохраняем URL в Redis
                        self.storage.save_channel_avatar(chat.id, cdn_url)
                        logger.info(f"Channel {chat.id} avatar saved to CDN successfully")
                    else:
                        logger.error(f"Failed to upload avatar to CDN for channel {chat.id}")
                else:
                    logger.warning(f"Could not download avatar for channel {chat.id}")
            else:
                logger.warning(f"No avatar found for channel {chat.id}")
                
        except Exception as e:
            logger.error(f"Error saving channel avatar: {str(e)}")

    async def _upload_to_cdn(self, file_data: bytes, filename: str) -> str:
        """Upload file to CDN and return URL"""
        try:
            async with aiohttp.ClientSession() as session:
                # Создаем FormData для загрузки файла
                data = aiohttp.FormData()
                data.add_field('file',
                             file_data,
                             filename=filename,
                             content_type='image/jpeg')
                
                # Добавляем API ключ в заголовки
                headers = {
                    'Authorization': f'Bearer {Config.CDN_API_KEY}'
                }
                
                # Отправляем файл на CDN
                async with session.post(
                    f"{Config.CDN_URL}/upload",
                    data=data,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('url')  # Предполагаем, что CDN возвращает URL в поле 'url'
                    else:
                        logger.error(f"CDN upload failed with status {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"Error uploading to CDN: {str(e)}")
            return None

    async def _handle_bot_kicked(self, event: events.ChatAction.Event, me: User) -> None:
        """Handle bot being removed from a channel"""
        try:
            if event.user_id == me.id:
                chat_id = self._normalize_channel_id(event.chat_id)
                kicked_by = event.original_update.actor_id
                
                users = self.storage.get_users_with_channel(chat_id)
                for user_id in users:
                    self.storage.remove_channel_for_user(user_id, chat_id)

                logger.info(f"Bot was removed from channel {chat_id} by user {kicked_by}")

        except Exception as e:
            logger.error(f"Error handling bot removal: {str(e)}") 