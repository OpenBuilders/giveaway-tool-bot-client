from typing import TYPE_CHECKING
from telethon import events
from telethon.tl.types import User, Channel, ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.tl.types import ChannelParticipantsAdmins
from loguru import logger
import json
from urllib.request import urlopen
from urllib.parse import urlencode
from ..config import Config

if TYPE_CHECKING:
    from ..bot import Bot


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

                    # Сохраняем информацию о канале
                    self.storage.save_channel_title(chat_id, chat.title)
                    self.storage.save_channel_username(chat_id, chat.username or "")

                    # Сохраняем URL: публичный t.me для public, инвайт для private
                    url_to_save = ""
                    if chat.username:
                        url_to_save = f"https://t.me/{chat.username}"
                    else:
                        try:
                            base = f"https://api.telegram.org/bot{Config.BOT_TOKEN}"
                            qs = urlencode({"chat_id": chat_id})
                            with urlopen(f"{base}/exportChatInviteLink?{qs}") as resp:
                                data = json.loads(resp.read().decode("utf-8"))
                            if data.get("ok") and data.get("result"):
                                url_to_save = data["result"]
                            else:
                                raise RuntimeError(data)
                        except Exception as e:
                            logger.warning(f"Failed to export invite link for channel {chat_id}: {str(e)}")
                            url_to_save = ""
                    self.storage.save_channel_url(chat_id, url_to_save)

                    # Получаем URL аватара канала из Bot API (если есть)
                    try:
                        bot_token = Config.BOT_TOKEN
                        if bot_token:
                            base = f"https://api.telegram.org/bot{bot_token}"
                            # getChat -> photo file_ids
                            get_chat_qs = urlencode({"chat_id": chat_id})
                            with urlopen(f"{base}/getChat?{get_chat_qs}") as resp:
                                data = json.loads(resp.read().decode("utf-8"))
                            if data.get("ok") and data["result"].get("photo"):
                                photo = data["result"]["photo"]
                                small_id = photo.get("small_file_id")
                                big_id = photo.get("big_file_id")
                                small_url = ""
                                big_url = ""
                                if small_id:
                                    qs = urlencode({"file_id": small_id})
                                    with urlopen(f"{base}/getFile?{qs}") as f1:
                                        f1d = json.loads(f1.read().decode("utf-8"))
                                    if f1d.get("ok") and f1d["result"].get("file_path"):
                                        small_url = f"https://api.telegram.org/file/bot{bot_token}/{f1d['result']['file_path']}"
                                if big_id:
                                    qs = urlencode({"file_id": big_id})
                                    with urlopen(f"{base}/getFile?{qs}") as f2:
                                        f2d = json.loads(f2.read().decode("utf-8"))
                                    if f2d.get("ok") and f2d["result"].get("file_path"):
                                        big_url = f"https://api.telegram.org/file/bot{bot_token}/{f2d['result']['file_path']}"

                                if small_url:
                                    self.storage.save_channel_photo_small_url(chat_id, small_url)
                                if big_url:
                                    self.storage.save_channel_photo_big_url(chat_id, big_url)
                    except Exception as e:
                        # Возможны ошибки сети/доступа; просто логируем
                        logger.warning(f"Failed to fetch channel photo URLs for {chat_id}: {str(e)}")
                    
                    # Получаем и сохраняем администраторов
                    admins = await self._get_channel_admins(chat)
                    for admin_id in admins:
                        self.storage.add_channel_for_user(admin_id, chat_id)
                        logger.info(f"Added channel {chat_id} for admin {admin_id}")
                    
                    self.storage.add_channel_for_user(user_id, chat_id)
                    logger.info(f"Bot was added to channel {chat_id} ({chat.title}) by user {user_id}")

        except Exception as e:
            logger.error(f"Error handling bot addition: {str(e)}")

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