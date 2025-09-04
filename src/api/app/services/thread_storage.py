import os
import abc
import pickle
import base64
import logging
import os
import abc
import pickle
import base64
import logging
from typing import Any, Optional, TypeVar, Generic
from semantic_kernel.agents import ChatHistoryAgentThread

logger = logging.getLogger(__name__)

T = TypeVar('T')

class SerializableThread:
    """
    A serializable wrapper for threads that can't be directly pickled.
    Used primarily for AzureAIAgentThread which contains non-picklable components.
    """
    
    def __init__(self, thread_type: str, thread_id: str = None, messages: list = None, metadata: dict = None):
        """
        Initialize a serializable thread wrapper.
        
        Args:
            thread_type: The type of thread this represents (e.g., "AzureAIAgentThread", "ChatHistoryAgentThread")
            thread_id: The thread ID used by the service (for AzureAIAgentThread)
            messages: The chat messages (for ChatHistoryAgentThread with reducers)
            metadata: Optional metadata to store with the thread
        """
        self.thread_type = thread_type
        self.thread_id = thread_id
        self.messages = messages or []
        self.metadata = metadata or {}

async def create_serializable_thread_copy(thread):
    """
    Create a serializable representation of a thread by extracting its messages.
    
    Args:
        thread: The original thread that may contain non-serializable components
        
    Returns:
        A dictionary representation that can be safely pickled
    """
    if hasattr(thread, '__class__') and thread.__class__.__name__ == "ChatHistoryAgentThread":
        # Extract messages using the async generator
        messages = []
        try:
            async for message in thread.get_messages():
                messages.append(message)
        except Exception as e:
            logger.warning(f"Could not retrieve messages from thread {thread.id}: {e}")
            messages = []
        
        # Create a simple dictionary representation that's picklable
        thread_data = {
            'thread_type': 'ChatHistoryAgentThread',
            'thread_id': getattr(thread, 'id', None),
            'messages': messages
        }
        
        logger.info(f"Created serializable representation for ChatHistoryAgentThread {getattr(thread, 'id', 'unknown')} with {len(messages)} messages")
        if messages:
            logger.debug(f"Sample messages in thread {getattr(thread, 'id', 'unknown')}: {[f'[{msg.role}] {msg.content[:50]}...' for msg in messages[:3]]}")
        return thread_data
    
    # For other thread types, return as-is (they should already be serializable)
    return thread

def restore_thread_from_serializable(thread_data):
    """
    Restore a thread object from a dictionary representation.
    
    Args:
        thread_data: A dictionary containing thread data or the original thread object
        
    Returns:
        A reconstructed thread object with stored_messages attribute if applicable
    """
    logger.debug(f"restore_thread_from_serializable called with: {type(thread_data)}")
    
    if isinstance(thread_data, dict) and thread_data.get('thread_type') == 'ChatHistoryAgentThread':
        logger.debug(f"ChatHistoryAgentThread dict detected with {len(thread_data.get('messages', []))} messages")
        
        # Create a new empty thread
        new_thread = ChatHistoryAgentThread()
        logger.debug(f"Created new_thread: {type(new_thread)}")
        
        # Add stored messages as an attribute that the chat service can access
        new_thread._stored_messages = thread_data.get('messages', [])
        new_thread._original_thread_id = thread_data.get('thread_id')
        
        logger.info(f"Restored ChatHistoryAgentThread with {len(thread_data.get('messages', []))} stored messages available")
        if thread_data.get('messages'):
            logger.debug(f"Sample restored messages: {[f'[{msg.role}] {msg.content[:50]}...' for msg in thread_data.get('messages', [])[:3]]}")
        
        logger.debug(f"Returning new_thread: {type(new_thread)}")
        return new_thread
    elif isinstance(thread_data, SerializableThread):
        # Handle legacy SerializableThread objects for backward compatibility
        logger.debug(f"SerializableThread detected, thread_type: {thread_data.thread_type}")
        if thread_data.thread_type == "ChatHistoryAgentThread":
            new_thread = ChatHistoryAgentThread()
            new_thread._stored_messages = thread_data.messages
            new_thread._original_thread_id = thread_data.thread_id
            
            logger.info(f"Restored ChatHistoryAgentThread with {len(thread_data.messages)} stored messages available")
            logger.debug(f"Returning new_thread: {type(new_thread)}")
            return new_thread
    
    # If not a thread dict/object, return as-is
    logger.debug(f"Not a ChatHistoryAgentThread representation, returning as-is: {type(thread_data)}")
    return thread_data

# Global storage that persists across instances
_GLOBAL_MEMORY_STORAGE = {}

class ThreadStorage(Generic[T], abc.ABC):
    """Abstract base class for thread storage implementations."""
    
    @abc.abstractmethod
    async def save(self, session_id: str, thread: T) -> None:
        """Save thread to storage."""
        pass
        
    @abc.abstractmethod
    async def load(self, session_id: str) -> Optional[T]:
        """Load thread from storage."""
        pass
        
    @abc.abstractmethod
    async def delete(self, session_id: str) -> None:
        """Delete thread from storage."""
        pass


class InMemoryThreadStorage(ThreadStorage[T]):
    """In-memory implementation of thread storage for development.
    Uses a global variable to persist data across multiple instances until server restart.
    """
    
    def __init__(self, use_serialization: bool = False):
        # Use the global dictionary instead of instance-level storage
        global _GLOBAL_MEMORY_STORAGE
        self._storage = _GLOBAL_MEMORY_STORAGE
        self.use_serialization = use_serialization
        
    async def save(self, session_id: str, thread: T) -> None:
        """Save thread to in-memory storage."""
        try:
            # Special handling for AzureAIAgentThread
            if hasattr(thread, '__class__') and thread.__class__.__name__ == "AzureAIAgentThread":
                thread_id = getattr(thread, "id", None)
                if thread_id:
                    serializable = {
                        'thread_type': "AzureAIAgentThread",
                        'thread_id': thread_id,
                        'messages': []
                    }
                    # Use serialization for the dictionary
                    serialized_bytes = pickle.dumps(serializable)
                    serialized_thread = base64.b64encode(serialized_bytes).decode('ascii') if self.use_serialization else serializable
                    self._storage[session_id] = serialized_thread
                    logger.debug(f"Saved AzureAIAgentThread ID {thread_id} for session {session_id} to memory")
                    return
                else:
                    logger.warning(f"AzureAIAgentThread has no ID, cannot save for session {session_id}")
                    return
            
            # Create a clean, serializable copy for all other thread types
            clean_thread = await create_serializable_thread_copy(thread)
            
            # Regular serialization for other thread types
            if self.use_serialization:
                # Use base64 encoding for consistency with other storage methods
                serialized_bytes = pickle.dumps(clean_thread)
                serialized_thread = base64.b64encode(serialized_bytes).decode('ascii')
                self._storage[session_id] = serialized_thread
            else:
                # Store directly for better performance in development
                self._storage[session_id] = clean_thread
                
            logger.debug(f"Saved thread for session {session_id} to memory")
        except Exception as e:
            logger.error(f"Error saving thread to memory: {str(e)}", exc_info=True)
        
    async def load(self, session_id: str) -> Optional[T]:
        """Load thread from in-memory storage."""
        data = self._storage.get(session_id)
        
        if data:
            try:
                if self.use_serialization:
                    # Deserialize with base64 decoding
                    binary_data = base64.b64decode(data)
                    thread = pickle.loads(binary_data)
                else:
                    thread = data
                
                # Handle thread restoration from dictionary or legacy SerializableThread
                thread = restore_thread_from_serializable(thread)
                
                if hasattr(thread, '_stored_messages'):
                    logger.info(f"Successfully loaded thread with {len(thread._stored_messages)} stored messages for session {session_id}")
                else:
                    logger.info(f"Loaded thread for session {session_id} (no stored messages)")
                    
                logger.debug(f"Loaded thread for session {session_id} from memory")
                return thread
            except Exception as e:
                logger.error(f"Error loading thread from memory: {str(e)}", exc_info=True)
                return None
                
        return None

    async def delete(self, session_id: str) -> None:
        """Delete thread from storage."""
        if session_id in self._storage:
            del self._storage[session_id]
            logger.debug(f"Deleted thread for session {session_id} from memory")


class RedisThreadStorage(ThreadStorage[T]):
    """Redis implementation of thread storage."""
    
    def __init__(self, connection_string: str, ttl_seconds: int = 86400):
        self.connection_string = connection_string
        self.ttl_seconds = ttl_seconds
        self._redis_client = None
        
    async def _get_client(self):
        """Lazy initialization of Redis client."""
        if self._redis_client is None:
            try:
                import redis.asyncio as redis
                self._redis_client = redis.from_url(self.connection_string)
            except ImportError:
                raise ImportError("redis package is required for RedisThreadStorage. Install it with: pip install redis")
        return self._redis_client
        
    async def save(self, session_id: str, thread: T) -> None:
        """Save thread to Redis."""
        try:
            client = await self._get_client()
            
            # Special handling for AzureAIAgentThread
            if hasattr(thread, '__class__') and thread.__class__.__name__ == "AzureAIAgentThread":
                thread_id = getattr(thread, "id", None)
                if thread_id:
                    serializable = {
                        'thread_type': "AzureAIAgentThread",
                        'thread_id': thread_id,
                        'messages': []
                    }
                    # Serialize the dictionary instead of the thread
                    serialized_bytes = pickle.dumps(serializable)
                    serialized_thread = base64.b64encode(serialized_bytes).decode('ascii')
                    
                    key = f"thread:{session_id}"
                    await client.set(key, serialized_thread, ex=self.ttl_seconds)
                    logger.info(f"Saved AzureAIAgentThread ID {thread_id} for session {session_id} to Redis")
                    return
                else:
                    logger.warning(f"AzureAIAgentThread has no ID, cannot save for session {session_id}")
                    return
            
            # Create a clean, serializable copy for all other thread types
            clean_thread = await create_serializable_thread_copy(thread)
            
            # Use base64 encoding for consistent serialization
            serialized_bytes = pickle.dumps(clean_thread)
            serialized_thread = base64.b64encode(serialized_bytes).decode('ascii')
            
            key = f"thread:{session_id}"
            await client.set(key, serialized_thread, ex=self.ttl_seconds)
            logger.info(f"Saved thread for session {session_id} to Redis")
        except Exception as e:
            logger.error(f"Failed to save thread to Redis: {str(e)}", exc_info=True)
            raise
            
    async def load(self, session_id: str) -> Optional[T]:
        """Load thread from Redis."""
        try:
            client = await self._get_client()
            key = f"thread:{session_id}"
            serialized_thread = await client.get(key)
            
            if serialized_thread:
                # Deserialize with base64 decoding
                binary_data = base64.b64decode(serialized_thread)
                thread = pickle.loads(binary_data)
                
                # Handle thread restoration from dictionary or legacy SerializableThread
                thread = restore_thread_from_serializable(thread)
                
                if hasattr(thread, '_stored_messages'):
                    logger.info(f"Successfully loaded thread with {len(thread._stored_messages)} stored messages for session {session_id} from Redis")
                else:
                    logger.info(f"Loaded thread for session {session_id} from Redis (no stored messages)")
                return thread
            return None
        except Exception as e:
            logger.error(f"Failed to load thread from Redis: {str(e)}", exc_info=True)
            return None


class CosmosDbThreadStorage(ThreadStorage[T]):
    """Azure Cosmos DB implementation of thread storage."""
    
    def __init__(self, connection_string: str = None, 
                 endpoint: str = None, 
                 database_name: str = "aiagents-db",
                 container_name: str = "chatHistory",
                 partition_key: str = "sessionId",  # Add default parameter
                 ttl_seconds: int = 86400):
        self.connection_string = connection_string
        self.endpoint = endpoint
        self.database_name = database_name
        self.container_name = container_name
        self.partition_key = partition_key
        self.ttl_seconds = ttl_seconds
        self._container = None
        
    async def _get_container(self):
        """Lazy initialization of Cosmos DB container."""
        if self._container is None:
            from azure.cosmos.aio import CosmosClient
            from azure.identity.aio import DefaultAzureCredential
            
            # If connection string is provided, use it
            if self.connection_string:
                client = CosmosClient.from_connection_string(self.connection_string)
            # Otherwise use managed identity with endpoint
            elif self.endpoint:
                credential = DefaultAzureCredential()
                client = CosmosClient(self.endpoint, credential)
            else:
                raise ValueError("Either connection_string or endpoint must be provided")
                
            # Get or create database
            database = client.get_database_client(self.database_name)
            try:
                await database.read()
            except Exception as e:
                raise PermissionError(f"Database '{self.database_name}' does not exist or permission denied: {str(e)}")
                
            # Get or create container with TTL enabled
            container_properties = {
                'id': self.container_name,
                'partitionKey': {
                    'paths': [f'/{self.partition_key}'],  # Use configurable partition key
                    'kind': 'Hash'
                },
                'default_ttl': self.ttl_seconds
            }
            
            try:
                self._container = database.get_container_client(self.container_name)
                await self._container.read()
            except Exception as e:
                raise PermissionError(f"Container  '{self.container_name}' does not exist or permission denied: {str(e)}")
                
        return self._container
        
    async def save(self, session_id: str, thread: T) -> None:
        """Save thread to Cosmos DB."""
        try:
            container = await self._get_container()
            
            # Special handling for AzureAIAgentThread
            if hasattr(thread, '__class__') and thread.__class__.__name__ == "AzureAIAgentThread":
                thread_id = getattr(thread, "id", None)
                if thread_id:
                    serializable = {
                        'thread_type': "AzureAIAgentThread",
                        'thread_id': thread_id,
                        'messages': []
                    }
                    # Serialize the wrapper instead of the thread
                    serialized_bytes = pickle.dumps(serializable)
                    serialized_thread = base64.b64encode(serialized_bytes).decode('ascii')
                    
                    # Create document with configurable partition key
                    document = {
                        'id': session_id,
                        self.partition_key: session_id,
                        'thread': serialized_thread,
                        'ttl': self.ttl_seconds
                    }
                    
                    # Upsert the document
                    await container.upsert_item(document)
                    logger.info(f"Saved AzureAIAgentThread ID {thread_id} for session {session_id} to Cosmos DB")
                    return
                else:
                    logger.warning(f"AzureAIAgentThread has no ID, cannot save for session {session_id}")
                    return
            
            # Create a clean, serializable copy for all other thread types
            clean_thread = await create_serializable_thread_copy(thread)
            
            # Direct pickle serialization for clean threads
            try:
                # Serialize the clean thread using base64 encoding for better compatibility
                serialized_bytes = pickle.dumps(clean_thread)
                serialized_thread = base64.b64encode(serialized_bytes).decode('ascii')
                
                # Create document with configurable partition key
                document = {
                    'id': session_id,
                    self.partition_key: session_id,
                    'thread': serialized_thread,
                    'ttl': self.ttl_seconds
                }
                
                # Upsert the document
                await container.upsert_item(document)
                logger.info(f"Saved {type(clean_thread).__name__} for session {session_id} to Cosmos DB")
                
            except Exception as pickle_error:
                logger.error(f"Failed to serialize clean thread for session {session_id}: {str(pickle_error)}")
                # Final fallback: save only essential thread state as dictionary
                if hasattr(clean_thread, 'chat_history') and hasattr(clean_thread.chat_history, 'messages'):
                    logger.info(f"Attempting to save thread messages only for session {session_id}")
                    serializable = {
                        'thread_type': clean_thread.__class__.__name__,
                        'thread_id': None,
                        'messages': [msg for msg in clean_thread.chat_history.messages] if clean_thread.chat_history.messages else []
                    }
                    serialized_bytes = pickle.dumps(serializable)
                    serialized_thread = base64.b64encode(serialized_bytes).decode('ascii')
                    
                    document = {
                        'id': session_id,
                        self.partition_key: session_id,
                        'thread': serialized_thread,
                        'ttl': self.ttl_seconds
                    }
                    
                    await container.upsert_item(document)
                    logger.info(f"Saved thread messages fallback for session {session_id} to Cosmos DB")
                else:
                    raise pickle_error
            logger.info(f"Saved thread for session {session_id} to Cosmos DB")
            
        except Exception as e:
            logger.error(f"Failed to save thread to Cosmos DB: {str(e)}", exc_info=True)
            raise
            
    async def load(self, session_id: str) -> Optional[T]:
        """Load thread from Cosmos DB."""
        try:
            container = await self._get_container()
            
            # Query for the document using configurable partition key
            query = f"SELECT * FROM c WHERE c.{self.partition_key} = '{session_id}'"
            items = [item async for item in container.query_items(
                query=query
            )]
            
            if items:
                # Deserialize the thread using base64 decoding
                serialized_thread = items[0]['thread']
                binary_data = base64.b64decode(serialized_thread)
                thread = pickle.loads(binary_data)
                logger.debug(f"Deserialized thread from pickle: {type(thread)}")
                
                # Handle thread restoration from dictionary or legacy SerializableThread
                thread = restore_thread_from_serializable(thread)
                logger.debug(f"After restore_thread_from_serializable: {type(thread)}")
                
                if hasattr(thread, '_stored_messages'):
                    logger.info(f"Successfully loaded thread with {len(thread._stored_messages)} stored messages for session {session_id} from Cosmos DB")
                else:
                    logger.info(f"Loaded thread for session {session_id} from Cosmos DB (no stored messages)")
                
                logger.debug(f"Final thread being returned: {type(thread)}")
                return thread
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to load thread from Cosmos DB: {str(e)}", exc_info=True)
            return None
            
    async def delete(self, session_id: str) -> None:
        """Delete thread from Cosmos DB."""
        try:
            container = await self._get_container()
            
            # Delete the document using configurable partition key
            await container.delete_item(session_id, partition_key=session_id)
            logger.info(f"Deleted thread for session {session_id} from Cosmos DB")
            
        except Exception as e:
            logger.error(f"Failed to delete thread from Cosmos DB: {str(e)}", exc_info=True)