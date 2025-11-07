from typing import Set, Optional, Dict
from redis import Redis
from .config import Config
import json

class RedisStorage:
    def __init__(self) -> None:
        """Initialize Redis connection"""
        self.redis_client: Redis = Redis(
            host=Config.REDIS_HOST,
            port=Config.REDIS_PORT,
            db=Config.REDIS_DB,
            decode_responses=True
        )

    def get_bot_session(self) -> Optional[str]:
        """Get StringSession for the bot from Redis"""
        return self.redis_client.get("bot:session")

    def save_bot_session(self, session: str) -> None:
        """Save StringSession for the bot to Redis"""
        self.redis_client.set("bot:session", session)

    def add_channel_for_user(self, user_id: int, channel_id: int) -> None:
        """Add channel to user's channel list"""
        key = f"user:{user_id}:channels"
        self.redis_client.sadd(key, channel_id)

    def remove_channel_for_user(self, user_id: int, channel_id: int) -> None:
        """Remove channel from user's channel list"""
        key = f"user:{user_id}:channels"
        self.redis_client.srem(key, channel_id)

    def get_user_channels(self, user_id: int) -> Set[int]:
        """Get list of channels for a user"""
        key = f"user:{user_id}:channels"
        channels = self.redis_client.smembers(key)
        return {int(channel) for channel in channels}

    def get_users_with_channel(self, channel_id: int) -> Set[int]:
        """Get all users who have this channel in their list"""
        pattern = "user:*:channels"
        users: Set[int] = set()
        
        for key in self.redis_client.scan_iter(match=pattern):
            user_id = int(key.split(":")[1])
            if str(channel_id) in self.redis_client.smembers(key):
                users.add(user_id)
                
        return users

    def save_channel_title(self, channel_id: int, title: str) -> None:
        """Save channel title to Redis"""
        key = f"channel:{channel_id}:title"
        self.redis_client.set(key, title)

    def get_channel_title(self, channel_id: int) -> Optional[str]:
        """Get channel title from Redis"""
        key = f"channel:{channel_id}:title"
        return self.redis_client.get(key)

    def save_channel_username(self, channel_id: int, username: str) -> None:
        """Save channel username to Redis"""
        key = f"channel:{channel_id}:username"
        self.redis_client.set(key, username)

    def get_channel_username(self, channel_id: int) -> Optional[str]:
        """Get channel username from Redis"""
        key = f"channel:{channel_id}:username"
        return self.redis_client.get(key) 

    def save_channel_url(self, channel_id: int, url: str) -> None:
        """Save channel URL (public t.me link or private invite) to Redis"""
        key = f"channel:{channel_id}:url"
        self.redis_client.set(key, url)

    def get_channel_url(self, channel_id: int) -> Optional[str]:
        """Get channel URL (public t.me link or private invite) from Redis"""
        key = f"channel:{channel_id}:url"
        return self.redis_client.get(key)

    def save_channel_photo_small_url(self, channel_id: int, url: str) -> None:
        """Save small profile photo URL for the channel to Redis"""
        key = f"channel:{channel_id}:photo_small_url"
        self.redis_client.set(key, url)

    def get_channel_photo_small_url(self, channel_id: int) -> Optional[str]:
        """Get small profile photo URL for the channel from Redis"""
        key = f"channel:{channel_id}:photo_small_url"
        return self.redis_client.get(key)

    def save_channel_photo_big_url(self, channel_id: int, url: str) -> None:
        """Save big profile photo URL for the channel to Redis"""
        key = f"channel:{channel_id}:photo_big_url"
        self.redis_client.set(key, url)

    def get_channel_photo_big_url(self, channel_id: int) -> Optional[str]:
        """Get big profile photo URL for the channel from Redis"""
        key = f"channel:{channel_id}:photo_big_url"
        return self.redis_client.get(key)

    # ---- Chat boosts - упрощенная структура с хранением по ключу канала ----
    def add_channel_boost_user(self, channel_id: int, user_id: int) -> None:
        """Добавить пользователя в список тех, кто пробустил канал.
        
        Структура: channel:{channel_id}:boost_users содержит Set user_id
        """
        key = f"channel:{channel_id}:boost_users"
        self.redis_client.sadd(key, int(user_id))

    def remove_channel_boost_user(self, channel_id: int, user_id: int) -> None:
        """Удалить пользователя из списка тех, кто пробустил канал."""
        key = f"channel:{channel_id}:boost_users"
        self.redis_client.srem(key, int(user_id))

    def has_channel_boost_user(self, channel_id: int, user_id: int) -> bool:
        """Проверить, есть ли пользователь в списке пробустивших канал."""
        key = f"channel:{channel_id}:boost_users"
        return bool(self.redis_client.sismember(key, int(user_id)))

    def get_channel_boost_users(self, channel_id: int) -> Set[int]:
        """Получить всех пользователей, которые пробустили канал."""
        key = f"channel:{channel_id}:boost_users"
        members = self.redis_client.smembers(key)
        return {int(uid) for uid in members}
    
    # ---- Детальная информация о бустах (опционально, для истории) ----
    def save_chat_boost_details(self, channel_id: int, boost_id: str, user_id: int,
                                 add_date: Optional[int], expire_date: Optional[int], payload: Dict) -> None:
        """Сохранить детальную информацию о бусте (опционально)."""
        boost_key = f"boost:{boost_id}"
        self.redis_client.hset(boost_key, mapping={
            "channel_id": channel_id,
            "user_id": user_id,
            "add_date": add_date if add_date is not None else "",
            "expire_date": expire_date if expire_date is not None else "",
            "status": "active",
            "raw": json.dumps(payload, ensure_ascii=False),
        })

    def remove_chat_boost_details(self, boost_id: str, remove_date: Optional[int], payload: Dict) -> None:
        """Обновить информацию о бусте как удаленном (опционально)."""
        boost_key = f"boost:{boost_id}"
        mapping = {
            "remove_date": remove_date if remove_date is not None else "",
            "status": "removed",
            "raw_removed": json.dumps(payload, ensure_ascii=False),
        }
        self.redis_client.hset(boost_key, mapping=mapping)