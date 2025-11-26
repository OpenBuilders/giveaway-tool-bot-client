from typing import TYPE_CHECKING, Optional
from telethon import events, Button, types
from loguru import logger
import os

if TYPE_CHECKING:
    from ..bot import Bot

from ..config import Config

class CommandHandler:
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.client = bot.client
        self.video_path = "media/Giveaway.mp4"

    async def register(self) -> None:
        """Register all command handlers"""
        self.client.add_event_handler(
            self._start_command,
            events.NewMessage(pattern='/start')
        )

    async def _upload_and_cache_video(self) -> Optional[types.InputFile]:
        """Загрузить видео из media и сохранить в кэш"""
        try:
            if not os.path.exists(self.video_path):
                logger.error(f"Video file not found: {self.video_path}")
                return None
            
            logger.info(f"Uploading {self.video_path} to Telegram servers...")
            uploaded = await self.client.upload_file(self.video_path)
            
            data = {
                "id": uploaded.id,
                "parts": uploaded.parts,
                "name": uploaded.name,
                "type": "input_file"
            }
            if hasattr(uploaded, 'md5_checksum'):
                data['md5'] = uploaded.md5_checksum
            
            self.bot.storage.save_start_video(data)
            logger.info("Video uploaded and cached successfully")
            
            if hasattr(uploaded, 'md5_checksum'):
                return types.InputFile(
                    id=uploaded.id,
                    parts=uploaded.parts,
                    name=uploaded.name,
                    md5_checksum=uploaded.md5_checksum
                )
            else:
                return types.InputFileBig(
                    id=uploaded.id,
                    parts=uploaded.parts,
                    name=uploaded.name
                )
        except Exception as e:
            logger.error(f"Failed to upload and cache video: {e}")
            return None

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

            file_to_send = None
            use_cached = False
            
            # Пытаемся использовать кэш
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
                        use_cached = True
                        logger.info("Using cached video")
                except Exception as e:
                    logger.warning(f"Failed to reconstruct cached video: {e}, will upload from media")
                    # Очищаем невалидный кэш
                    self.bot.storage.delete_start_video()
            
            # Если кэша нет, загружаем из media
            if not file_to_send:
                logger.info("No cache found, uploading video from media")
                file_to_send = await self._upload_and_cache_video()
            
            # Если не удалось загрузить, используем путь к файлу напрямую
            if not file_to_send:
                if os.path.exists(self.video_path):
                    file_to_send = self.video_path
                    logger.info("Using video file path directly")
                else:
                    logger.error(f"Video file not found: {self.video_path}")
                    raise FileNotFoundError(f"Video file not found: {self.video_path}")
            
            try:
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
            except Exception as send_error:
                # Если кэшированное видео не работает, загружаем заново из media
                if use_cached:
                    logger.warning(f"Failed to send cached video: {send_error}, uploading from media")
                    # Очищаем невалидный кэш
                    self.bot.storage.delete_start_video()
                    # Загружаем и кэшируем заново
                    file_to_send = await self._upload_and_cache_video()
                    if not file_to_send:
                        if os.path.exists(self.video_path):
                            file_to_send = self.video_path
                        else:
                            raise FileNotFoundError(f"Video file not found: {self.video_path}")
                    
                    # Повторная попытка отправки
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
                else:
                    # Если это уже была попытка с файлом из media, пробрасываем ошибку дальше
                    raise
        except Exception as e:
            logger.error(f"Error handling start command: {str(e)}") 