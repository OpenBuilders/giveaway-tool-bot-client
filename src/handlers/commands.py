from typing import TYPE_CHECKING
from telethon import events, Button
from loguru import logger

if TYPE_CHECKING:
    from ..bot import Bot

from ..config import Config

class CommandHandler:
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.client = bot.client

    async def register(self) -> None:
        """Register all command handlers"""
        self.client.add_event_handler(
            self._start_command,
            events.NewMessage(pattern='/start')
        )

    async def _start_command(self, event: events.NewMessage.Event) -> None:
        """Handle /start command"""
        try:
            button = Button.url("Create Giveaway", Config.APP_URL)
            await event.respond(
                "Wassssssup",
                buttons=button
            )
        except Exception as e:
            logger.error(f"Error handling start command: {str(e)}") 