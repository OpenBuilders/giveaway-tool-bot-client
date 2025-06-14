from typing import List, Set, Optional
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

    def save_channel_avatar(self, channel_id: int, avatar_url: str) -> None:
        """Save channel avatar URL to Redis"""
        key = f"channel:{channel_id}:avatar"
        self.redis_client.set(key, avatar_url)

    def get_channel_avatar(self, channel_id: int) -> Optional[str]:
        """Get channel avatar URL from Redis"""
        key = f"channel:{channel_id}:avatar"
        return self.redis_client.get(key) 