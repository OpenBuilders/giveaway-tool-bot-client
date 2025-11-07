from typing import TYPE_CHECKING
import asyncio
from telethon import events
from telethon.tl.types import User, Channel, ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.tl.types import UpdateChannelParticipant, PeerChannel
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
        self._boost_updates_offset = 0

    async def register(self) -> None:
        """Register all chat event handlers"""
        self.client.add_event_handler(
            self._handle_chat_action,
            events.ChatAction
        )
        self.client.add_event_handler(
            self._handle_new_event,
        )
        # Start background polling of Bot API updates for chat boost events
        try:
            self.client.loop.create_task(self._poll_bot_boost_updates())
        except Exception as e:
            logger.warning(f"Failed to start boost updates polling: {str(e)}")
        
    async def _handle_new_event(self, event) -> None:
        """Handle new event"""
        logger.info(f"New event: {event}")
        try:
            # Handle the case when the bot is re-added to a channel after being removed
            if isinstance(event, UpdateChannelParticipant):
                me = await self.client.get_me()
                new_participant = getattr(event, 'new_participant', None)
                new_participant_user_id = getattr(new_participant, 'user_id', None)

                if new_participant_user_id == me.id:
                    # Bot was (re)added to the channel
                    channel: Channel = await self.client.get_entity(PeerChannel(event.channel_id))
                    chat_id = self._normalize_channel_id(channel.id)
                    actor_id = getattr(event, 'actor_id', None)

                    # Save channel basic info
                    self.storage.save_channel_title(chat_id, channel.title)
                    self.storage.save_channel_username(chat_id, channel.username or "")

                    # Save URL: public t.me for public channels; invite for private
                    url_to_save = ""
                    if channel.username:
                        url_to_save = f"https://t.me/{channel.username}"
                    else:
                        try:
                            base = f"https://api.telegram.org/bot{Config.BOT_TOKEN}"
                            # 1) Try to get primary invite via getChat
                            get_chat_qs = urlencode({"chat_id": chat_id})
                            with urlopen(f"{base}/getChat?{get_chat_qs}") as resp:
                                chat_data = json.loads(resp.read().decode("utf-8"))
                            invite_link = chat_data.get("result", {}).get("invite_link") if chat_data.get("ok") else None
                            if invite_link:
                                url_to_save = invite_link
                            else:
                                # 2) Create a new invite link
                                create_qs = urlencode({"chat_id": chat_id})
                                with urlopen(f"{base}/createChatInviteLink?{create_qs}") as resp2:
                                    create_data = json.loads(resp2.read().decode("utf-8"))
                                if create_data.get("ok") and create_data.get("result", {}).get("invite_link"):
                                    url_to_save = create_data["result"]["invite_link"]
                                else:
                                    # 3) Fallback to exportChatInviteLink
                                    export_qs = urlencode({"chat_id": chat_id})
                                    with urlopen(f"{base}/exportChatInviteLink?{export_qs}") as resp3:
                                        export_data = json.loads(resp3.read().decode("utf-8"))
                                    if export_data.get("ok") and export_data.get("result"):
                                        url_to_save = export_data["result"]
                                    else:
                                        raise RuntimeError({
                                            "getChat": chat_data,
                                            "createChatInviteLink": create_data,
                                            "exportChatInviteLink": export_data,
                                        })
                        except Exception as e:
                            logger.warning(f"Failed to export invite link for channel {chat_id}: {str(e)}")
                            url_to_save = ""
                    self.storage.save_channel_url(chat_id, url_to_save)
                    if url_to_save:
                        logger.info(f"Saved invite URL for channel {chat_id}")

                    # Fetch and save channel avatar URLs (if any)
                    try:
                        bot_token = Config.BOT_TOKEN
                        if bot_token:
                            base = f"https://api.telegram.org/bot{bot_token}"
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
                        logger.warning(f"Failed to fetch channel photo URLs for {chat_id}: {str(e)}")

                    # Save admins as channel owners in storage
                    admins = await self._get_channel_admins(channel)
                    for admin_id in admins:
                        self.storage.add_channel_for_user(admin_id, chat_id)
                        logger.info(f"Added channel {chat_id} for admin {admin_id}")

                    # Also attribute channel to the actor who re-added the bot (if available)
                    if actor_id:
                        self.storage.add_channel_for_user(actor_id, chat_id)
                    logger.info(f"Bot was (re)added to channel {chat_id} ({channel.title}) by user {actor_id}")
        except Exception as e:
            logger.error(f"Error in new event handler: {str(e)}")

    def _normalize_channel_id(self, channel_id: int) -> int:
        """Convert any channel ID format to -100 prefix format"""
        str_id = str(channel_id)
        if not str_id.startswith('-100'):
            return int(f'-100{str_id}')
        return channel_id

    async def _handle_chat_action(self, event: events.ChatAction.Event) -> None:
        """Handle bot being added to or removed from a chat"""
        logger.info(f"Chat action event: {event}")
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
                            # 1) Пытаемся получить текущую primary invite ссылку через getChat
                            get_chat_qs = urlencode({"chat_id": chat_id})
                            with urlopen(f"{base}/getChat?{get_chat_qs}") as resp:
                                chat_data = json.loads(resp.read().decode("utf-8"))
                            invite_link = chat_data.get("result", {}).get("invite_link") if chat_data.get("ok") else None
                            if invite_link:
                                url_to_save = invite_link
                            else:
                                # 2) Если нет — создаём новую через createChatInviteLink (современный метод)
                                create_qs = urlencode({"chat_id": chat_id})
                                with urlopen(f"{base}/createChatInviteLink?{create_qs}") as resp2:
                                    create_data = json.loads(resp2.read().decode("utf-8"))
                                if create_data.get("ok") and create_data.get("result", {}).get("invite_link"):
                                    url_to_save = create_data["result"]["invite_link"]
                                else:
                                    # 3) На крайний случай пробуем exportChatInviteLink (устаревший для SG/каналов)
                                    export_qs = urlencode({"chat_id": chat_id})
                                    with urlopen(f"{base}/exportChatInviteLink?{export_qs}") as resp3:
                                        export_data = json.loads(resp3.read().decode("utf-8"))
                                    if export_data.get("ok") and export_data.get("result"):
                                        url_to_save = export_data["result"]
                                    else:
                                        raise RuntimeError({
                                            "getChat": chat_data,
                                            "createChatInviteLink": create_data,
                                            "exportChatInviteLink": export_data,
                                        })
                        except Exception as e:
                            logger.warning(f"Failed to export invite link for channel {chat_id}: {str(e)}")
                            url_to_save = ""
                    self.storage.save_channel_url(chat_id, url_to_save)
                    if url_to_save:
                        logger.info(f"Saved invite URL for channel {chat_id}")

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
                print("users", users)
                for user_id in users:
                    print("user_id", user_id)
                    self.storage.remove_channel_for_user(user_id, chat_id)

                logger.info(f"Bot was removed from channel {chat_id} by user {kicked_by}")

        except Exception as e:
            logger.error(f"Error handling bot removal: {str(e)}") 

    async def _poll_bot_boost_updates(self) -> None:
        """Continuously poll Bot API for chat boost updates and handle them."""
        base = f"https://api.telegram.org/bot{Config.BOT_TOKEN}"
        while True:
            try:
                qs = urlencode({
                    "timeout": 50,
                    "offset": self._boost_updates_offset,
                    "allowed_updates": json.dumps(["chat_boost", "removed_chat_boost"]),
                })
                # Run blocking urlopen in a thread to avoid blocking the event loop
                def _fetch():
                    with urlopen(f"{base}/getUpdates?{qs}") as resp:
                        return json.loads(resp.read().decode("utf-8"))

                data = await asyncio.get_running_loop().run_in_executor(None, _fetch)

                if not data.get("ok"):
                    await asyncio.sleep(2)
                    continue

                for upd in data.get("result", []):
                    self._boost_updates_offset = max(self._boost_updates_offset, upd.get("update_id", 0) + 1)

                    if "chat_boost" in upd:
                        await self._handle_chat_boost_update(upd["chat_boost"])
                    elif "removed_chat_boost" in upd:
                        await self._handle_removed_chat_boost_update(upd["removed_chat_boost"])

            except Exception as e:
                logger.warning(f"Error polling chat boost updates: {str(e)}")
                await asyncio.sleep(3)

    async def _handle_chat_boost_update(self, chat_boost: dict) -> None:
        """Handle Bot API chat_boost update payload."""
        try:
            chat = chat_boost.get("chat", {})
            boost = chat_boost.get("boost", {})
            chat_id = chat.get("id")
            source = boost.get("source", {}) if isinstance(boost, dict) else {}
            user = source.get("user") if isinstance(source, dict) else None
            user_id = user.get("id") if isinstance(user, dict) else None

            norm_chat_id = self._normalize_channel_id(chat_id) if chat_id is not None else chat_id

            boost_id = boost.get("boost_id") if isinstance(boost, dict) else None
            add_date = boost.get("add_date") if isinstance(boost, dict) else None
            expire_date = boost.get("expire_date") if isinstance(boost, dict) else None

            if not boost_id or user_id is None or norm_chat_id is None:
                logger.warning(f"chat_boost missing identifiers: boost_id={boost_id}, user_id={user_id}, chat_id={norm_chat_id}")
                return

            # Добавляем пользователя в список пробустивших канал
            self.storage.add_channel_boost_user(norm_chat_id, int(user_id))
            
            # Опционально сохраняем детальную информацию о бусте
            self.storage.save_chat_boost_details(norm_chat_id, str(boost_id), int(user_id), add_date, expire_date, chat_boost)

            logger.info(f"Chat boost received for chat {norm_chat_id} from user {user_id} (boost_id={boost_id})")
        except Exception as e:
            logger.error(f"Failed to handle chat_boost update: {str(e)}")

    async def _handle_removed_chat_boost_update(self, removed: dict) -> None:
        """Handle Bot API removed_chat_boost update payload."""
        try:
            chat = removed.get("chat", {})
            chat_id = chat.get("id")
            norm_chat_id = self._normalize_channel_id(chat_id) if chat_id is not None else chat_id

            boost_id = removed.get("boost_id")
            remove_date = removed.get("remove_date")
            source = removed.get("source", {}) if isinstance(removed, dict) else {}
            user = source.get("user") if isinstance(source, dict) else None
            user_id = user.get("id") if isinstance(user, dict) else None

            if not boost_id or user_id is None or norm_chat_id is None:
                logger.warning(f"removed_chat_boost missing identifiers: boost_id={boost_id}, user_id={user_id}, chat_id={norm_chat_id}")
                return

            # Удаляем пользователя из списка пробустивших канал
            self.storage.remove_channel_boost_user(norm_chat_id, int(user_id))
            
            # Опционально обновляем детальную информацию о бусте
            self.storage.remove_chat_boost_details(str(boost_id), remove_date, removed)

            logger.info(f"Chat boost removed in chat {norm_chat_id} for user {user_id} (boost_id={boost_id})")
        except Exception as e:
            logger.error(f"Failed to handle removed_chat_boost update: {str(e)}")