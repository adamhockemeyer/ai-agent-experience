# app/services/file_processor.py
import base64
import logging
import tempfile
import os
import io
from typing import Optional, Dict, Any, Tuple, TYPE_CHECKING
from pathlib import Path

if TYPE_CHECKING:
    from app.models import Attachment

try:
    from markitdown import MarkItDown
except ImportError:
    MarkItDown = None

logger = logging.getLogger(__name__)

class FileProcessor:
    """Service for processing various file types into formats suitable for AI agents."""
    
    def __init__(self):
        self.markitdown = MarkItDown() if MarkItDown else None
        if not self.markitdown:
            logger.warning("MarkItDown not available. Non-image files will not be processed.")
    
    def is_image_type(self, mime_type: str) -> bool:
        """Check if the file is an image type."""
        return mime_type.startswith('image/')
    
    def is_processable_type(self, mime_type: str) -> bool:
        """Check if the file type can be processed by MarkItDown."""
        if self.is_image_type(mime_type):
            return True
        
        if not self.markitdown:
            return False
        
        # Common types that MarkItDown can handle
        processable_types = {
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'text/plain',
            'text/csv',
            'text/html',
            'text/markdown',
            'application/json',
            'application/xml',
            'text/javascript',
            'text/css',
            'application/javascript',
        }
        
        return mime_type in processable_types
    
    async def process_file_attachment(self, attachment: 'Attachment') -> Tuple[str, Dict[str, Any]]:
        """
        Process a file attachment and return the content and metadata.
        
        Returns:
            Tuple of (processed_content, metadata)
            - For images: returns base64 data and image metadata
            - For other files: returns markdown content and file metadata
        """
        try:
            if self.is_image_type(attachment.type):
                return await self._process_image(attachment)
            else:
                return await self._process_document(attachment)
        except Exception as e:
            logger.error(f"Error processing file {attachment.name}: {str(e)}")
            # Return error information
            return f"[Error processing file '{attachment.name}': {str(e)}]", {
                "type": "error",
                "file_name": attachment.name,
                "mime_type": attachment.type
            }
    
    async def _process_image(self, attachment: 'Attachment') -> Tuple[str, Dict[str, Any]]:
        """Process image attachments."""
        # Extract base64 data from data URL if needed
        if attachment.url.startswith('data:') and ';base64,' in attachment.url:
            base64_data = attachment.url.split(';base64,', 1)[1]
        else:
            base64_data = attachment.url
        
        return base64_data, {
            "type": "image",
            "file_name": attachment.name,
            "mime_type": attachment.type,
            "data_format": "base64"
        }
      
    async def _process_document(self, attachment: 'Attachment') -> Tuple[str, Dict[str, Any]]:
        """Process document attachments using MarkItDown."""
        if not self.markitdown:
            return f"[File '{attachment.name}' could not be processed - MarkItDown not available]", {
                "type": "error",
                "file_name": attachment.name,
                "mime_type": attachment.type
            }
        
        try:
            # Log initial attachment data for debugging
            logger.info(f"Processing document {attachment.name}")
            logger.info(f"Attachment type: {attachment.type}")
            logger.info(f"URL starts with 'data:': {attachment.url.startswith('data:')}")
            logger.info(f"URL contains ';base64,': {';base64,' in attachment.url}")
            
            # Log first 100 characters of URL for debugging (but not the full data)
            url_preview = attachment.url[:100] + "..." if len(attachment.url) > 100 else attachment.url
            logger.info(f"URL preview: {url_preview}")
            
            # Decode base64 data
            if attachment.url.startswith('data:') and ';base64,' in attachment.url:
                logger.info("Extracting base64 data from data URL")
                base64_data = attachment.url.split(';base64,', 1)[1]
                logger.info(f"Base64 data length after extraction: {len(base64_data)}")
            else:
                logger.info("Using URL as raw base64 data")
                base64_data = attachment.url
                logger.info(f"Raw base64 data length: {len(base64_data)}")
            
            # Log first few characters of base64 data
            base64_preview = base64_data[:50] + "..." if len(base64_data) > 50 else base64_data
            logger.info(f"Base64 data preview: {base64_preview}")
            
            try:
                file_data = base64.b64decode(base64_data)
                logger.info(f"Successfully decoded base64. File data length: {len(file_data)} bytes")
                
                # Log first few bytes as hex for debugging
                hex_preview = file_data[:20].hex() if len(file_data) >= 20 else file_data.hex()
                logger.info(f"File data hex preview: {hex_preview}")
                
                # Try to identify file type from the first few bytes
                if file_data.startswith(b'{'):
                    logger.info("File appears to start with '{' - likely JSON")
                elif file_data.startswith(b'PK'):
                    logger.info("File appears to start with 'PK' - likely ZIP/Office document")
                elif file_data.startswith(b'%PDF'):
                    logger.info("File appears to start with '%PDF' - likely PDF")
                else:
                    logger.info(f"File starts with: {file_data[:10]}")
                    
            except Exception as decode_error:
                logger.error(f"Failed to decode base64 data: {decode_error}")
                return f"[Error: Invalid base64 data for {attachment.name}]", {
                    "type": "error",
                    "file_name": attachment.name,
                    "mime_type": attachment.type,
                    "error_message": f"Base64 decode error: {str(decode_error)}"
                }
            
            # Try using BytesIO first (more efficient, no temp files)
            try:
                logger.info("Attempting to process with BytesIO")
                file_stream = io.BytesIO(file_data)
                file_stream.name = attachment.name  # Some converters need a filename
                logger.info(f"Created BytesIO stream with name: {file_stream.name}")
                
                result = self.markitdown.convert(file_stream)
                markdown_content = result.text_content if hasattr(result, 'text_content') else str(result)
                logger.info(f"Successfully processed {attachment.name} using BytesIO")
                logger.info(f"Markdown content length: {len(markdown_content)}")
                
            except Exception as stream_error:
                logger.warning(f"BytesIO approach failed for {attachment.name}: {stream_error}")
                logger.info("Falling back to temporary file approach")
                
                # Fallback to temporary file approach
                with tempfile.NamedTemporaryFile(delete=False, suffix=self._get_file_extension(attachment.name)) as temp_file:
                    logger.info(f"Created temporary file: {temp_file.name}")
                    temp_file.write(file_data)
                    temp_file_path = temp_file.name
                    logger.info(f"Wrote {len(file_data)} bytes to temporary file")
                
                try:
                    logger.info(f"Attempting to convert temporary file: {temp_file_path}")
                    result = self.markitdown.convert(temp_file_path)
                    markdown_content = result.text_content if hasattr(result, 'text_content') else str(result)
                    logger.info(f"Successfully processed {attachment.name} using temporary file")
                    logger.info(f"Markdown content length: {len(markdown_content)}")
                except Exception as temp_error:
                    logger.error(f"Temporary file approach also failed: {temp_error}")
                    raise temp_error
                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_file_path)
                        logger.info(f"Cleaned up temporary file: {temp_file_path}")
                    except Exception as cleanup_error:
                        logger.warning(f"Could not clean up temp file {temp_file_path}: {cleanup_error}")
            
            # Add file information header
            file_header = f"# File: {attachment.name}\n\n"
            if attachment.type:
                file_header += f"**File Type:** {attachment.type}\n\n"
            
            full_content = file_header + markdown_content
            logger.info(f"Generated full content for {attachment.name}, total length: {len(full_content)}")
            
            return full_content, {
                "type": "document",
                "file_name": attachment.name,
                "mime_type": attachment.type,
                "processed_format": "markdown"
            }
        
        except Exception as e:
            logger.error(f"Error processing document {attachment.name}: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return f"[Error processing file '{attachment.name}': {str(e)}]", {
                "type": "error",
                "file_name": attachment.name,
                "mime_type": attachment.type
            }
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        return Path(filename).suffix or '.tmp'
