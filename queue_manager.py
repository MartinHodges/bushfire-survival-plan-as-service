from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import asyncio
import redis.asyncio as redis
import logging

logger = logging.getLogger(__name__)

class QueueManager(ABC):
    """Abstract queue manager for pluggable queue technologies"""
    
    @abstractmethod
    async def publish_outbound(self, session_id: str, message: Dict[str, Any]):
        """Publish message to outbound queue for BFF"""
        pass
    
    @abstractmethod
    async def consume_inbound(self, callback):
        """Consume messages from inbound queue"""
        pass
    
    @abstractmethod
    async def acquire_processing_lock(self, session_id: str) -> bool:
        """Acquire exclusive processing lock for session"""
        pass
    
    @abstractmethod
    async def release_processing_lock(self, session_id: str):
        """Release processing lock for session"""
        pass

class RedisQueueManager(QueueManager):
    """Redis implementation of queue manager"""
    
    def __init__(self, redis_client):
        self.redis_client = redis_client
        self.inbound_queue = "backend_inbound"
        self.outbound_queue = "backend_outbound"
    
    async def initialize_queues(self):
        """Initialize Redis connection - pub/sub channels need no setup"""
        try:
            # Test Redis connection
            await self.redis_client.ping()
            logger.info("Redis connection established, queues ready")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def publish_outbound(self, session_id: str, message: Dict[str, Any]):
        """Publish message to outbound channel for all BFF instances"""
        message["session_id"] = session_id
        await self.redis_client.publish(self.outbound_queue, json.dumps(message))
        logger.debug(f"[{session_id}] Published to outbound: {message['type']}")
    
    async def consume_inbound(self, callback):
        """Subscribe to inbound channel - all backend instances receive all messages"""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(self.inbound_queue)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        data = json.loads(message["data"])
                        session_id = data.get("session_id")
                        
                        if session_id:
                            # All instances get message, but only one processes via lock
                            asyncio.create_task(callback(session_id, data))
                        else:
                            logger.warning("Message missing session_id")
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in message: {e}")
                        
        except Exception as e:
            logger.error(f"Error consuming inbound channel: {e}")
        finally:
            await pubsub.unsubscribe(self.inbound_queue)
            await pubsub.close()
    
    async def acquire_processing_lock(self, session_id: str) -> bool:
        """Acquire exclusive processing lock for session"""
        lock_key = f"processing_lock:{session_id}"
        return await self.redis_client.set(lock_key, "locked", nx=True, ex=60)
    
    async def release_processing_lock(self, session_id: str):
        """Release processing lock for session"""
        lock_key = f"processing_lock:{session_id}"
        await self.redis_client.delete(lock_key)