# app/services/function_call_stream.py
import asyncio
import logging
import json
from typing import Dict, Any, AsyncGenerator
from opentelemetry import trace

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

class FunctionCallStream:
    """
    A stream for handling function call events in real-time.
    This class decouples function call reporting from the PluginManager lifecycle,
    allowing function calls to be reported as they happen.
    """
    
    # Singleton pattern to track streams by session_id
    _instances: Dict[str, 'FunctionCallStream'] = {}
    
    @classmethod
    def get_or_create(cls, session_id: str) -> 'FunctionCallStream':
        """Get an existing stream for a session ID or create a new one."""
        if session_id not in cls._instances:
            cls._instances[session_id] = FunctionCallStream(session_id)
        return cls._instances[session_id]
    
    @classmethod
    def cleanup(cls, session_id: str) -> None:
        """Remove a stream from the tracking dictionary."""
        if session_id in cls._instances:
            cls._instances[session_id].close()
            del cls._instances[session_id]
            logger.debug(f"Cleaned up function call stream for session {session_id}")
    
    def __init__(self, session_id: str):
        """Initialize the function call stream for a session."""
        self.session_id = session_id
        self.queue = asyncio.Queue()
        self.is_active = True
    
    def add_function_call(self, call_info: Dict[str, Any]) -> None:
        """Add a function call event to the stream."""
        if not self.is_active:
            logger.warning(f"Attempted to add function call to inactive stream: {self.session_id}")
            return
            
        try:
            # Add the event to the queue
            self.queue.put_nowait(call_info)
            logger.debug(f"Added function call event to stream: {call_info.get('function', '')}")
        except Exception as e:
            logger.error(f"Error adding function call to stream: {str(e)}")
    
    async def get_events(self) -> AsyncGenerator[str, None]:
        """
        Get function call events as they are added to the stream.
        This is an async generator that yields formatted function call events.
        """
        with tracer.start_as_current_span("function_call_stream"):
            while self.is_active or not self.queue.empty():
                try:
                    # Try to get an event with a short timeout to allow checking is_active
                    try:
                        call_info = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                    except asyncio.TimeoutError:
                        # No events in queue, check if we should continue
                        if not self.is_active and self.queue.empty():
                            break
                        continue
                        
                    # Format the event based on call type
                    if call_info["type"] == "function_start":
                        yield self._format_function_start(call_info)
                        
                    elif call_info["type"] == "function_end":
                        yield self._format_function_end(call_info)
                        
                    # Mark the task as done
                    self.queue.task_done()
                        
                except Exception as e:
                    logger.error(f"Error processing function call event: {str(e)}")
                    continue
    
    def close(self) -> None:
        """
        Mark the stream as inactive, which will allow the get_events generator
        to finish after processing any remaining events.
        """
        self.is_active = False
        logger.debug(f"Marked function call stream as inactive: {self.session_id}")
    
    def _format_function_start(self, call_info: Dict[str, Any]) -> str:
        """Format a function start event using markdown details/summary tags."""
        plugin = call_info.get("plugin", "")
        function = call_info.get("function", "")
        prefix = "[AUTO] " if call_info.get("is_auto") == "Auto" else ""
        
        # Create the summary line with an emoji and function name
        summary = f"🔄 {prefix}Calling {plugin}.{function}"
        
        # Format the arguments as pretty JSON for the details section
        details = ""
        if call_info.get("arguments"):
            try:
                # Format JSON with indentation for better readability
                formatted_args = json.dumps(call_info["arguments"], indent=2, ensure_ascii=False)
                details = f"\n```json\n{formatted_args}\n```\n"
            except Exception:
                # Fallback to simple string representation if JSON formatting fails
                details = f"\n```\n{str(call_info['arguments'])}\n```\n"
        
        # Build the complete markdown with details/summary tags
        message = f"<details>\n<summary>{summary}</summary>\n{details}</details>\n\n"
        return message
    
    def _format_function_end(self, call_info: Dict[str, Any]) -> str:
        """Format a function end event using markdown details/summary tags."""
        status = call_info.get("status", "")
        status_emoji = "✅" if status == "success" else "❌"
        plugin = call_info.get("plugin", "")
        function = call_info.get("function", "")
        prefix = "[AUTO] " if call_info.get("is_auto") == "Auto" else ""
        
        # Calculate duration if timestamps are available
        duration_text = ""
        if "timestamp" in call_info and "start_timestamp" in call_info:
            end_time = call_info["timestamp"]
            start_time = call_info["start_timestamp"]
            # Calculate duration in seconds
            duration_secs = end_time - start_time
            # Format based on duration length
            if duration_secs < 0.001:
                duration_text = f"{duration_secs * 1_000_000:.0f}μs"  # microseconds
            elif duration_secs < 1:
                duration_text = f"{duration_secs * 1_000:.0f}ms"  # milliseconds
            else:
                duration_text = f"{duration_secs:.2f}s"  # seconds
        
        # Create the summary line with status emoji, function name, and duration
        summary = f"{status_emoji} {prefix}Completed {plugin}.{function}"
        if duration_text:
            summary += f" ({duration_text})"
        
        # Format the result for the details section if available
        result_details = ""
        if "result" in call_info:
            try:
                # Try to parse result as JSON for prettier formatting
                result_obj = json.loads(call_info["result"]) if isinstance(call_info["result"], str) else call_info["result"]
                formatted_result = json.dumps(result_obj, indent=2, ensure_ascii=False)
                result_details = f"\n**Result:**\n```json\n{formatted_result}\n```\n"
            except (json.JSONDecodeError, TypeError):
                # If not valid JSON, just show as plain text
                result_details = f"\n**Result:**\n```\n{call_info['result']}\n```\n"
        
        # Include status and duration in the details
        status_text = "Success" if status == "success" else f"Error: {status}"
        details = f"\n**Status:** {status_text}"
        if duration_text:
            details += f"\n**Duration:** {duration_text}"
        details += result_details
        
        # Build the complete markdown with details/summary tags
        message = f"<details>\n<summary>{summary}</summary>{details}</details>\n\n"
        return message