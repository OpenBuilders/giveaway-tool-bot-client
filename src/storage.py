from typing import Set, Optional
from redis import Redis
from .config import Config

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