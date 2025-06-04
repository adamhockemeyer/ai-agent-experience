# app/services/file_processor.py
import base64
import logging
import tempfile
import os
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
            # Decode base64 data
            if attachment.url.startswith('data:') and ';base64,' in attachment.url:
                base64_data = attachment.url.split(';base64,', 1)[1]
            else:
                base64_data = attachment.url
            
            file_data = base64.b64decode(base64_data)
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=self._get_file_extension(attachment.name)) as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
            
            try:
                # Process with MarkItDown
                result = self.markitdown.convert(temp_file_path)
                markdown_content = result.text_content if hasattr(result, 'text_content') else str(result)
                
                # Add file information header
                file_header = f"# File: {attachment.name}\n\n"
                if attachment.type:
                    file_header += f"**File Type:** {attachment.type}\n\n"
                
                full_content = file_header + markdown_content
                
                return full_content, {
                    "type": "document",
                    "file_name": attachment.name,
                    "mime_type": attachment.type,
                    "processed_format": "markdown"
                }
            
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_file_path)
                except Exception as cleanup_error:
                    logger.warning(f"Could not clean up temp file {temp_file_path}: {cleanup_error}")
        
        except Exception as e:
            logger.error(f"Error processing document {attachment.name}: {str(e)}")
            return f"[Error processing file '{attachment.name}': {str(e)}]", {
                "type": "error",
                "file_name": attachment.name,
                "mime_type": attachment.type
            }
    
    def _get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        return Path(filename).suffix or '.tmp'
