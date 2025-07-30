"""
Display service implementation for G1 glasses
"""
import asyncio
from bleak import BleakClient
from typing import List, Optional
from utils.logger import setup_logger

class DisplayService:
    """Handles text and image display"""
    
    # Constants from documentation
    #MAX_WIDTH_PIXELS = 488
    #FONT_SIZE = 21
    LINES_PER_SCREEN = 5
    CHARS_PER_LINE = 55  # Slightly reduced from 60 to give some margin for word wrapping
    MAX_TEXT_LENGTH = CHARS_PER_LINE * LINES_PER_SCREEN  # About 275 characters
    
    def __init__(self, connector):
        self.connector = connector
        self.logger = setup_logger()
        self._current_text = None  # Track currently displayed text
        
    def _split_text_into_chunks(self, text: str) -> List[str]:
        """Split text into screen-sized chunks, preserving word boundaries"""
        chunks = []
        lines = []
        current_line = []
        current_length = 0
        
        words = text.split()
        
        for word in words:
            word_length = len(word)
            # Check if adding this word would exceed line length
            if current_length + word_length + (1 if current_line else 0) > self.CHARS_PER_LINE:
                # Save current line and start new one
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                current_line.append(word)
                current_length += word_length + (1 if current_line else 0)
        
        # Add last line if exists
        if current_line:
            lines.append(' '.join(current_line))
        
        # Combine lines into chunks that fit on screen
        current_chunk = []
        for line in lines:
            if len(current_chunk) >= self.LINES_PER_SCREEN:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
            current_chunk.append(line)
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks

    def validate_text(self, text: str) -> bool:
        """Validate text length and content"""
        if not text:
            raise ValueError("Text cannot be empty")
        return True

    async def send_text_sequential(self, text: str, hold_time: Optional[int] = None, show_exit: bool = True):
        """Send text to both glasses in sequence with acknowledgment"""
        # Keep existing connection checks
        if not self.connector.left_client.is_connected or not self.connector.right_client.is_connected:
            self.logger.error("One or both glasses disconnected. Please reconnect.")
            return False

        # Quick validation
        if not text:
            raise ValueError("Text cannot be empty")
            
        # Only chunk if text exceeds display limits
        chunks = self._split_text_into_chunks(text)
        text_to_send = chunks[0]  # Get first chunk with line breaks
            
        # Prepare command once for both glasses
        command = bytearray([
            0x4E,       # Text command
            0x00,       # Sequence number
            0x01,       # Total packages
            0x00,       # Current package
            0x71,       # Screen status (0x70 Text Show + 0x01 New Content)
            0x00, 0x00, # Character position
            0x00,       # Current page
            0x01,       # Max pages
        ])
        command.extend(text_to_send.encode('utf-8'))
        
        try:
            # Send to both glasses simultaneously
            tasks = [
                self.connector.uart_service.send_command_with_retry(self.connector.left_client, command),
                self.connector.uart_service.send_command_with_retry(self.connector.right_client, command)
            ]
            results = await asyncio.gather(*tasks)
            
            if all(results):
                if hold_time:
                    await asyncio.sleep(hold_time)
                    if show_exit:
                        await self.show_exit_message()
                return True
            else:
                self.logger.error("Failed to send to one or both glasses")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending text: {e}")
            return False

    async def display_text(self, text: str, hold_time: Optional[int] = None):
        """Display a single text with optional hold time"""
        self.validate_text(text)
        
        if len(text) <= self.MAX_TEXT_LENGTH:
            return await self.send_text_sequential(text, hold_time)
        else:
            self.logger.info("Text exceeds screen size, splitting into chunks...")
            chunks = self._split_text_into_chunks(text)
            return await self.display_text_sequence(chunks, hold_time)

    async def display_text_sequence(self, texts: List[str], hold_time: Optional[int] = 5):
        """Display a sequence of texts with specified hold time"""
        if not texts:
            raise ValueError("Text sequence cannot be empty")
            
        # Validate all texts first
        for text in texts:
            self.validate_text(text)
            if len(text) > self.MAX_TEXT_LENGTH:
                raise ValueError(f"Text exceeds maximum length of {self.MAX_TEXT_LENGTH} characters: {text[:50]}...")
        
        # Display each text in sequence
        for i, text in enumerate(texts, 1):
            self.logger.info(f"Displaying text {i} of {len(texts)}")
            show_exit = (i == len(texts))  # Only show exit on last text
            if not await self.send_text_sequential(text, hold_time, show_exit=show_exit):
                return False
                
        return True

    async def show_exit_message(self):
        """Display exit message and wait for user action"""
        if self._current_text != "Activity completed, double-tap to exit":
            await self.send_text_sequential("Activity completed, double-tap to exit", hold_time=3) 