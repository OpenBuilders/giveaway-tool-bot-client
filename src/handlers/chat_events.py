from typing import TYPE_CHECKING
from telethon import events, TelegramClient
from telethon.tl.types import User, Channel, ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.tl.functions.channels import GetParticipantsRequest, LeaveChannelRequest
from telethon.tl.types import ChannelParticipantsAdmins
from loguru import logger
import boto3
from botocore.config import Config as BotoConfig
import io

if TYPE_CHECKING:
    from ..bot import Bot

from ..config import Config

class ChatEventHandler:
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.client = bot.client
        self.storage = bot.storage
        
        # Инициализация S3 клиента
        self.s3_client = boto3.client(
            's3',
            endpoint_url=Config.S3_ENDPOINT,
            aws_access_key_id=Config.S3_ACCESS_KEY,
            aws_secret_access_key=Config.S3_SECRET_KEY,
            config=BotoConfig(signature_version='s3v4')
        )

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

    async def _get_channel_admins(self, chat: Channel) -> list[int]:
        """Get list of channel admin IDs"""
        try:
            admins = []
            async for participant in self.client.iter_participants(
                chat,
                filter=ChannelParticipantsAdmins
            ):
                if isinstance(participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
                    admins.append(participant.id)
            return admins
        except Exception as e:
            logger.error(f"Error getting channel admins: {str(e)}")
            return []

    async def _handle_bot_added(self, event: events.ChatAction.Event, me: User) -> None:
        """Handle bot being added to a channel"""
        try:
            if not event.action_message:
                new_participant = event.original_update.new_participant
                if new_participant and new_participant.user_id == me.id:
                    chat: Channel = await event.get_chat()
                    chat_id = self._normalize_channel_id(chat.id)
                    user_id = event.added_by.id

                    # Проверяем, является ли канал публичным
                    if not chat.username:
                        # Если канал не публичный, выходим из него
                        await self.client(LeaveChannelRequest(chat))
                        # Отправляем сообщение пользователю
                        await self.client.send_message(
                            user_id,
                            "Извините, но я могу работать только с публичными каналами. "
                            "Пожалуйста, сделайте канал публичным и добавьте меня снова."
                        )
                        logger.warning(f"Bot left private channel {chat_id} ({chat.title})")
                        return

                    # Сохраняем информацию о канале
                    self.storage.save_channel_title(chat_id, chat.title)
                    self.storage.save_channel_username(chat_id, chat.username)
                    
                    # Получаем и сохраняем администраторов
                    admins = await self._get_channel_admins(chat)
                    for admin_id in admins:
                        self.storage.add_channel_for_user(admin_id, chat_id)
                        logger.info(f"Added channel {chat_id} for admin {admin_id}")
                    
                    await self._save_channel_avatar(chat)
                    
                    self.storage.add_channel_for_user(user_id, chat_id)
                    logger.info(f"Bot was added to channel {chat_id} ({chat.title}) by user {user_id}")

        except Exception as e:
            logger.error(f"Error handling bot addition: {str(e)}")

    async def _save_channel_avatar(self, chat: Channel) -> None:
        """Save channel avatar to CDN and store URL in Redis"""
        try:
            photos = await self.client.get_profile_photos(chat)
            
            if photos:
                photo = photos[0]
                
                photo_data = await self.client.download_media(photo, bytes)
                
                if photo_data:
                    cdn_url = await self._upload_to_cdn(photo_data, f"channel_{chat.id}_avatar.jpg")
                    
                    if cdn_url:
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
        """Upload file to S3 CDN and return URL"""
        try:
            # Загружаем файл в S3
            self.s3_client.put_object(
                Bucket=Config.S3_BUCKET,
                Key=filename,
                Body=file_data,
                ContentType='image/jpeg',
                ACL='public-read'
            )
            
            # Формируем URL для CDN
            cdn_url = f"{Config.CDN_URL}/{filename}"
            return cdn_url
                        
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