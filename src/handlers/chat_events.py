from typing import TYPE_CHECKING
from telethon import events
from telethon.tl.types import User, Channel, ChannelParticipantAdmin, ChannelParticipantCreator
from telethon.tl.functions.channels import LeaveChannelRequest
from telethon.tl.types import ChannelParticipantsAdmins
from loguru import logger

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

                    # Check if the channel is public
                    if not chat.username:
                        # If the channel is not public, leave it
                        await self.client(LeaveChannelRequest(chat))
                        # Send a message to the user
                        #   "Sorry, I can only work with public channels. "
                        #   "Please make the channel public and add me again."
                        await self.client.send_message(
                            user_id,
                            "Извините, но я могу работать только с публичными каналами. "
                            "Пожалуйста, сделайте канал публичным и добавьте меня снова."
                        )
                        logger.warning(f"Bot left private channel {chat_id} ({chat.title})")
                        return

                    # Save channel information
                    self.storage.save_channel_title(chat_id, chat.title)
                    self.storage.save_channel_username(chat_id, chat.username)
                    
                    # Get and save administrators
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