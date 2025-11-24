from typing import TYPE_CHECKING
from telethon import events, Button, types
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
            text = (
                "<b>Giveaway bot</b>\n\n"
                "What I can do:\n"
                "🎁 Create and manage giveaways inside Telegram.\n"
                "👥 Let users join by completing simple tasks or meeting conditions.\n"
                "🏆 Pick winners automatically and distribute rewards.\n"
                "📊 Track participation and performance in real time.\n\n"
                "Built by independent developers for "
                "<a href='https://tools.tg/'>Telegram Tools</a>.\n\n"
                "Open source for the community:\n"
                "<a href='https://github.com/OpenBuilders/giveaway-tool-backend'>Github repository</a>"
            )

            buttons = [
                [Button.url("Create Giveaway", Config.APP_URL)],
                [Button.url("Explore Other Apps", "https://tools.tg/")],
            ]

            file_to_send = "https://cdn.giveaway.tools.tg/assets/Started.gif"
            
            cached_video = self.bot.storage.get_start_video()
            if cached_video:
                try:
                    if cached_video.get('type') == 'input_file':
                        if 'md5' in cached_video:
                            file_to_send = types.InputFile(
                                id=cached_video['id'],
                                parts=cached_video['parts'],
                                name=cached_video['name'],
                                md5_checksum=cached_video['md5']
                            )
                        else:
                            file_to_send = types.InputFileBig(
                                id=cached_video['id'],
                                parts=cached_video['parts'],
                                name=cached_video['name']
                            )
                except Exception as e:
                    logger.error(f"Failed to reconstruct cached video: {e}")
            
            # await self.client.send_file(
            #     event.chat_id,
            #     file=file_to_send,
            #     caption=text,
            #     buttons=buttons,
            #     parse_mode="HTML",
            #     attributes=[
            #         types.DocumentAttributeFilename(file_name='Started.gif'),
            #         types.DocumentAttributeAnimated()
            #     ]
            # )
            
            await self.client.send_message(
                event.chat_id,
                text,
                buttons=buttons,
                parse_mode="HTML",
                file=file_to_send,
                attributes=[
                    types.DocumentAttributeVideo(
                        duration=0, w=0, h=0, supports_streaming=True
                    )
                ],
            )
        except Exception as e:
            logger.error(f"Error handling start command: {str(e)}") 