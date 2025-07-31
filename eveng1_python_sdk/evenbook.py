"""
EvenBook - E-book Reader for G1 Smart Glasses
===========================================

A stylish e-book reader that allows you to:
- Browse and download free books from Project Gutenberg
- Read books on your G1 smart glasses with smooth scrolling
- Adjust reading speed (words per minute)
- Control reading with tap gestures (pause/exit)
- Manage your local book library

Author: EvenBook Team
Version: 1.0.0
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import json
import os
import re
import time
import asyncio
import threading
from typing import List, Optional
from dataclasses import dataclass
import sys

# G1 SDK imports
sys.path.insert(0, '.')
from connector import G1Connector
from utils.logger import setup_logger
from gutenberg_api import GutenbergClient, BookInfo
# StateEvent imported when needed in gesture handling

# Configure CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

@dataclass
class Book:
    """Data class for book information"""
    id: str
    title: str
    author: str
    language: str
    downloads: int
    text_url: str
    local_path: Optional[str] = None
    word_count: Optional[int] = None
    content: Optional[str] = None
    source: Optional[str] = None

@dataclass
class ReadingSession:
    """Data class for reading session state"""
    book: Book
    current_position: int = 0
    words_per_minute: int = 150
    is_paused: bool = False
    lines_per_screen: int = 4
    words_per_line: int = 12
    total_chunks: int = 0
    current_chunk_words: Optional[List[str]] = None
    word_index: int = 0
    start_time: float = 0
    reading_state: str = "waiting"  # "waiting", "countdown", "reading", "paused"
    
    def __post_init__(self):
        if self.current_chunk_words is None:
            self.current_chunk_words = []

class ProjectGutenbergAPI:
    """API client for Project Gutenberg"""
    
    def __init__(self):
        self.client = GutenbergClient()
    
    def search_books(self, query: str = "", language: str = "en", limit: int = 20) -> List[Book]:
        """Search for books in Project Gutenberg"""
        try:
            languages = [language] if language else None
            book_infos = self.client.search(query=query or None, languages=languages, page_size=limit)
            
            books = []
            for book_info in book_infos:
                # Convert BookInfo to Book
                author = ', '.join(book_info.authors) if book_info.authors else 'Unknown Author'
                language = book_info.languages[0] if book_info.languages else 'en'
                
                book = Book(
                    id=str(book_info.id),
                    title=book_info.title,
                    author=author,
                    language=language,
                    downloads=book_info.download_count,
                    text_url=book_info.text_url or ""
                )
                books.append(book)
            
            return books
            
        except Exception as e:
            print(f"Error searching books: {e}")
            return []
    
    def download_book(self, book: Book, download_dir: str = "books") -> bool:
        """Download a book's text content"""
        try:
            # Create books directory
            os.makedirs(download_dir, exist_ok=True)
            
            # Generate safe filename
            safe_title = re.sub(r'[^\w\s-]', '', book.title).strip()
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            safe_author = re.sub(r'[^\w\s-]', '', book.author).strip()
            safe_author = re.sub(r'[-\s]+', '-', safe_author)
            filename = f"{book.id}_{safe_title}_{safe_author}.txt"
            filepath = os.path.join(download_dir, filename)
            
            # Download the text using our client
            book_info = BookInfo(
                id=int(book.id),
                title=book.title,
                authors=[book.author],
                languages=[book.language],
                subjects=[],
                download_count=book.downloads,
                formats={'text/plain': book.text_url}
            )
            
            text_content = self.client.download_text(book_info)
            if not text_content:
                return False
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text_content)
            
            # Update book with local path
            book.local_path = filepath
            
            # Count words
            word_count = len(text_content.split())
            book.word_count = word_count
            
            return True
            
        except Exception as e:
            print(f"Error downloading book: {e}")
            return False

class TextProcessor:
    """Handles text processing for G1 display"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and prepare text for reading"""
        # Remove Project Gutenberg header/footer
        lines = text.split('\n')
        start_idx = 0
        end_idx = len(lines)
        
        # Find start of actual content
        for i, line in enumerate(lines):
            if '*** START' in line.upper() or 'START OF' in line.upper():
                start_idx = i + 1
                break
        
        # Find end of actual content
        for i in range(len(lines) - 1, -1, -1):
            if '*** END' in lines[i].upper() or 'END OF' in lines[i].upper():
                end_idx = i
                break
        
        # Extract main content
        content_lines = lines[start_idx:end_idx]
        text = '\n'.join(content_lines)
        
        # Clean up text
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Multiple empty lines
        text = re.sub(r'[ \t]+', ' ', text)  # Multiple spaces
        text = text.strip()
        
        return text
    
    @staticmethod
    def split_into_chunks(text: str, words_per_chunk: int = 48) -> List[str]:
        """Split text into readable chunks for G1 display"""
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), words_per_chunk):
            chunk_words = words[i:i + words_per_chunk]
            chunk = ' '.join(chunk_words)
            chunks.append(chunk)
        
        return chunks
    
    @staticmethod
    def format_for_display(chunk: str, lines_per_screen: int = 5, chars_per_line: int = 55) -> str:
        """Format text chunk for G1 display with exact specifications"""
        words = chunk.split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if len(test_line) <= chars_per_line:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        # Ensure we don't exceed lines per screen and pad to exact lines
        while len(lines) < lines_per_screen:
            lines.append("")  # Add empty lines
        
        if len(lines) > lines_per_screen:
            lines = lines[:lines_per_screen]
        
        return '\n'.join(lines)

class G1Reader:
    """Handles reading display on G1 glasses with gesture control and live preview"""
    
    def __init__(self, on_display_update=None, on_exit_callback=None):
        self.glasses: Optional[G1Connector] = None
        self.is_connected = False
        self.is_reading = False
        self.current_session: Optional[ReadingSession] = None
        self.reading_task = None
        self.countdown_task: Optional[asyncio.Task] = None
        self.logger = setup_logger()
        self.on_display_update = on_display_update  # Callback for live preview
        self._on_exit_callback = on_exit_callback  # Callback for double tap exit
        self.gesture_enabled = False
        
        # Reading state management
        self.current_display_text = ""
        self.highlighted_text = ""
        self._chunks = []
        self._on_progress_callback = None
        self._last_gesture_time = 0
        self._gesture_debounce_delay = 0.5  # 500ms debounce
        
        # Set up event loop for async operations
        self.loop = None
        self.thread = None
    
    def start_async_loop(self):
        """Start async event loop in separate thread"""
        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        
        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        
        # Wait for loop to start
        while self.loop is None:
            time.sleep(0.1)
    
    async def connect(self) -> bool:
        """Connect to G1 glasses and setup gesture handling"""
        try:
            self.glasses = G1Connector()
            connected = await self.glasses.connect()
            self.is_connected = connected
            
            if connected:
                # Setup gesture event handling
                await self._setup_gesture_handlers()
            
            return connected
        except Exception as e:
            self.logger.error(f"Failed to connect to G1: {e}")
            return False
    
    async def _setup_gesture_handlers(self):
        """Setup gesture event handlers for reading control"""
        try:
            # Method 1: Try state_manager (like in examples/interactions.py)
            if hasattr(self.glasses, 'state_manager') and self.glasses.state_manager:
                self.glasses.state_manager.add_raw_state_callback(self._handle_gesture_event)
                self.gesture_enabled = True
                self.logger.info("Gesture handlers setup via state_manager")
                return
            
            # Method 2: Try event_service if available
            if hasattr(self.glasses, 'event_service') and self.glasses.event_service:
                from utils.constants import EventCategories
                self.glasses.event_service.subscribe_raw(EventCategories.STATE, self._handle_gesture_event)
                self.gesture_enabled = True
                self.logger.info("Gesture handlers setup via event_service")
                return
            
            # Method 3: Try UART service direct callback (fallback)
            if hasattr(self.glasses, 'uart_service') and self.glasses.uart_service:
                self.glasses.uart_service.add_notification_callback(self._handle_gesture_event)
                self.gesture_enabled = True
                self.logger.info("Gesture handlers setup via uart_service")
                return
                
            self.logger.warning("No gesture handler method available")
            
        except Exception as e:
            self.logger.warning(f"Could not setup gesture handlers: {e}")
    
    async def _handle_gesture_event(self, state_code: int, side: str, label: str):
        """Handle gesture events from glasses - called by state_manager"""
        if not self.gesture_enabled:
            return
            
        try:
            # Check if this is an interaction event
            from utils.constants import StateEvent
            interaction_name, _ = StateEvent.get_interaction(state_code)
            
            self.logger.info(f"Gesture detected: {interaction_name} ({label}) from {side} side")
            
            # Debounce gestures to prevent rapid-fire triggering
            import time
            current_time = time.time()
            if current_time - self._last_gesture_time < self._gesture_debounce_delay:
                self.logger.info(f"Gesture debounced - too soon after last gesture ({current_time - self._last_gesture_time:.3f}s)")
                return
            
            self._last_gesture_time = current_time
            
            # Handle double tap from RIGHT glass for play/pause
            if interaction_name == "DOUBLE_TAP" and side == "right":
                await self._handle_play_pause()
            elif interaction_name == "DOUBLE_TAP" and side == "left":
                # Exit reading mode and update GUI  
                if self.current_session:
                    self.logger.info("Double tap LEFT detected - stopping reading")
                    self.stop_reading()
                    # Update GUI on main thread
                    if self._on_exit_callback:
                        self._on_exit_callback()
                
        except Exception as e:
            self.logger.error(f"Error handling gesture: {e}")
    
    async def _handle_play_pause(self):
        """Handle double tap RIGHT gesture for reading control (play/pause)"""
        if not self.current_session:
            self.logger.warning("_handle_play_pause called but no current_session")
            return
            
        session = self.current_session
        
        self.logger.info(f"_handle_play_pause called - current state: {session.reading_state}, is_paused: {session.is_paused}")
        
        if session.reading_state == "waiting":
            # First tap - start countdown
            self.logger.info("Starting countdown from waiting state")
            await self._start_countdown()
        elif session.reading_state == "countdown":
            # Ignore gestures during countdown
            self.logger.info("Gesture ignored during countdown")
            return
        elif session.reading_state == "reading":
            # Pause reading
            self.logger.info("Pausing reading - was in 'reading' state")
            session.reading_state = "paused"
            session.is_paused = True
            await self._update_display("PAUSED\n\nDouble tap RIGHT to resume")
            self.logger.info(f"Reading paused by double tap RIGHT - state changed from 'reading' to 'paused'")
        elif session.reading_state == "paused":
            # Resume reading
            self.logger.info("Resuming reading - was in 'paused' state")
            session.reading_state = "reading"
            session.is_paused = False
            self.logger.info(f"Reading resumed by double tap RIGHT - state changed from 'paused' to 'reading'")
        else:
            self.logger.warning(f"Unexpected reading state in _handle_play_pause: {session.reading_state}")
    
    async def _start_countdown(self):
        """Start 3-second countdown before reading begins"""
        if not self.current_session:
            return
            
        self.current_session.reading_state = "countdown"
        
        for i in range(3, 0, -1):
            countdown_text = f"STARTING IN\n\n{i}"
            await self._update_display(countdown_text)
            await asyncio.sleep(1)
        
        # Start reading
        self.logger.info(f"Countdown completed - transitioning from 'countdown' to 'reading'")
        self.current_session.reading_state = "reading"
        self.current_session.is_paused = False  # Ensure it's not paused
        self.current_session.start_time = time.time()
        
        self.logger.info(f"State after countdown: reading_state={self.current_session.reading_state}, is_paused={self.current_session.is_paused}")
        
        # Small delay to ensure any pending gestures are processed
        await asyncio.sleep(0.2)
        
        # Double-check the state hasn't changed due to race condition
        if self.current_session.reading_state != "reading":
            self.logger.warning(f"State changed unexpectedly after countdown: {self.current_session.reading_state}")
            self.current_session.reading_state = "reading"
            self.current_session.is_paused = False
        
        # Begin the reading process
        if self.reading_task:
            self.reading_task.cancel()
        self.reading_task = asyncio.create_task(self._continue_reading())
    
    async def _continue_reading(self):
        """Continue reading process with word-by-word highlighting"""
        if not self.current_session or not hasattr(self, '_chunks'):
            self.logger.error("Cannot continue reading: missing session or chunks")
            return
            
        session = self.current_session
        chunks = self._chunks
        
        self.logger.info(f"Starting _continue_reading - state: {session.reading_state}, is_paused: {session.is_paused}, is_reading: {self.is_reading}")
        
        try:
            start_chunk = min(session.current_position, len(chunks) - 1)
            
            for i in range(start_chunk, len(chunks)):
                self.logger.debug(f"Chunk {i}: reading_state={session.reading_state}, is_paused={session.is_paused}, is_reading={self.is_reading}")
                
                if not self.is_reading or session.reading_state != "reading":
                    self.logger.info(f"Breaking from reading loop: is_reading={self.is_reading}, reading_state={session.reading_state}")
                    break
                
                # Wait if paused
                while session.is_paused and self.is_reading:
                    await asyncio.sleep(0.1)
                
                if not self.is_reading or session.reading_state != "reading":
                    self.logger.info(f"Breaking after pause check: is_reading={self.is_reading}, reading_state={session.reading_state}")
                    break
                
                # Process chunk with word-by-word highlighting
                chunk_text = chunks[i]
                formatted_text = TextProcessor.format_for_display(chunk_text, session.lines_per_screen)
                
                await self._display_chunk_with_highlighting(formatted_text, session)
                
                # Update progress
                session.current_position = i + 1
                if self._on_progress_callback:
                    progress = (i + 1) / len(chunks) * 100
                    # Calculate stats for progress callback
                    total_words = len(' '.join(chunks).split())
                    estimated_time = total_words / session.words_per_minute
                    stats = {
                        'total_words': total_words,
                        'estimated_time': estimated_time,
                        'words_per_minute': session.words_per_minute
                    }
                    self._on_progress_callback(progress, i + 1, len(chunks), stats)
            
            # Reading completed
            if self.is_reading and session.reading_state == "reading":
                await self._update_display("Book completed!\n\nDouble-tap to exit")
                
        except Exception as e:
            self.logger.error(f"Error during reading: {e}")
    
    async def _display_chunk_with_highlighting(self, text: str, session: ReadingSession):
        """Display text chunk with word-by-word highlighting based on WPM"""
        words = text.split()
        if not words:
            return
            
        # Calculate timing per word
        time_per_word = 60.0 / session.words_per_minute
        
        # Display full text first
        await self._update_display(text)
        
        # Highlight words progressively
        for i, word in enumerate(words):
            if not self.is_reading or session.reading_state != "reading":
                break
                
            # Wait if paused
            while session.is_paused and self.is_reading:
                await asyncio.sleep(0.1)
            
            if not self.is_reading or session.reading_state != "reading":
                break
            
            # Create highlighted version (for preview)
            highlighted_words = words[:i+1]
            
            # Update live preview with highlighting
            if self.on_display_update:
                self.on_display_update(text, self._create_highlighted_text(text, highlighted_words))
            
            # Wait for word timing
            await asyncio.sleep(time_per_word)
    
    def _create_highlighted_text(self, text: str, highlighted_words: List[str]) -> str:
        """Create text with word highlighting for preview"""
        if not highlighted_words:
            return text
            
        words = text.split()
        result = []
        highlight_count = 0
        
        for word in words:
            if highlight_count < len(highlighted_words):
                result.append(f"[{word}]")  # Mark highlighted words
                highlight_count += 1
            else:
                result.append(word)
        
        return " ".join(result)
    
    async def _update_display(self, text: str, highlighted_words: Optional[List[str]] = None):
        """Update display on glasses and trigger live preview"""
        if not self.is_connected or not self.glasses:
            return
        
        # Store current display state
        self.current_display_text = text
        if highlighted_words:
            self.highlighted_text = self._create_highlighted_text(text, highlighted_words)
        else:
            self.highlighted_text = text
        
        # Update live preview in GUI
        if self.on_display_update:
            self.on_display_update(self.current_display_text, self.highlighted_text)
        
        try:
            # Try multiple methods to display text
            text_displayed = False
            
            # Method 1: Try glasses.display (like in working examples)
            if hasattr(self.glasses, 'display') and hasattr(self.glasses.display, 'display_text'):
                try:
                    await self.glasses.display.display_text(text)
                    text_displayed = True
                    self.logger.info(f"Text displayed via glasses.display: {text[:50]}...")
                except Exception as e:
                    self.logger.warning(f"glasses.display failed: {e}")
            
            # Method 2: Try display_service
            if not text_displayed and hasattr(self.glasses, 'display_service') and hasattr(self.glasses.display_service, 'display_text'):
                try:
                    await self.glasses.display_service.display_text(text)
                    text_displayed = True
                    self.logger.info(f"Text displayed via display_service: {text[:50]}...")
                except Exception as e:
                    self.logger.warning(f"Display service failed: {e}")
            
            # Method 3: Try command manager (more direct approach)
            if not text_displayed and hasattr(self.glasses, 'command_manager'):
                try:
                    # Send text command directly
                    await self.glasses.command_manager.send_text_command(text, 5.0)
                    text_displayed = True
                    self.logger.info(f"Text displayed via command_manager: {text[:50]}...")
                except Exception as e:
                    self.logger.warning(f"Command manager failed: {e}")
            
            # Method 4: Last resort - simulate by logging
            if not text_displayed:
                self.logger.warning(f"All display methods failed, simulating: {text}")
                # At least log what would be displayed
                print(f"[G1 DISPLAY SIMULATION] {text}")
                
        except Exception as e:
            self.logger.error(f"Error displaying text: {e}")
    
    async def disconnect(self):
        """Disconnect from G1 glasses"""
        if self.glasses and self.is_connected:
            await self.glasses.disconnect()
            self.is_connected = False
    
    def connect_sync(self) -> bool:
        """Synchronous wrapper for connect"""
        if not self.loop:
            self.start_async_loop()
        
        future = asyncio.run_coroutine_threadsafe(self.connect(), self.loop)
        return future.result(timeout=30)
    
    def disconnect_sync(self):
        """Synchronous wrapper for disconnect"""
        if self.loop and self.is_connected:
            future = asyncio.run_coroutine_threadsafe(self.disconnect(), self.loop)
            future.result(timeout=10)
    
    async def start_reading(self, session: ReadingSession, on_progress_callback=None):
        """Start reading a book with gesture control and word highlighting"""
        self.current_session = session
        self.is_reading = True
        
        try:
            # Load book content
            if not session.book.local_path:
                raise ValueError("Book has no local path")
            with open(session.book.local_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Process text
            clean_content = TextProcessor.clean_text(content)
            chunks = TextProcessor.split_into_chunks(clean_content, words_per_chunk=50)  # Slightly more words
            session.total_chunks = len(chunks)
            
            # Calculate book statistics
            total_words = len(clean_content.split())
            estimated_time = total_words / session.words_per_minute
            
            # Show initial instructions (no emojis to avoid encoding issues)
            initial_text = f"EVENBOOK: {session.book.title}\n\nTotal: {session.total_chunks} slides\nEst. time: {estimated_time:.1f} min\n\nDouble tap RIGHT to start"
            await self._update_display(initial_text)
            
            # Wait for user to start reading
            session.reading_state = "waiting"
            
            # Progress callback with book stats
            if on_progress_callback:
                on_progress_callback(0, 0, session.total_chunks, {
                    'total_words': total_words,
                    'estimated_time': estimated_time,
                    'words_per_minute': session.words_per_minute
                })
            
            # Store chunks for reading process
            self._chunks = chunks
            self._on_progress_callback = on_progress_callback
            
            # The actual reading will be handled by gesture events
            # This function sets up the session and waits
            while self.is_reading and session.reading_state in ["waiting", "countdown"]:
                await asyncio.sleep(0.1)
            
        except Exception as e:
            self.logger.error(f"Error starting reading: {e}")
            self.is_reading = False
            self.current_session = None
    
    def start_reading_sync(self, session: ReadingSession, on_progress_callback=None):
        """Synchronous wrapper for start_reading"""
        if not self.loop:
            self.start_async_loop()
        
        # Cancel existing reading task
        if self.reading_task and not self.reading_task.done():
            self.reading_task.cancel()
        
        # Start new reading task
        self.reading_task = asyncio.run_coroutine_threadsafe(
            self.start_reading(session, on_progress_callback), 
            self.loop
        )
    
    def pause_reading(self):
        """Pause/resume reading"""
        if self.current_session:
            self.current_session.is_paused = not self.current_session.is_paused
    
    def stop_reading(self):
        """Stop reading"""
        self.is_reading = False
        if self.current_session:
            self.current_session.is_paused = False
            self.current_session.reading_state = "waiting"

class ProgressDialog:
    """Modal progress dialog that cannot be closed by user"""
    
    def __init__(self, parent, title, main_app):
        self.parent = parent
        self.main_app = main_app
        
        # Create modal dialog
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("400x200")
        self.dialog.resizable(False, False)
        
        # Make it modal and unescapable
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self.do_nothing)  # Disable X button
        
        # Center on screen
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (400 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (200 // 2)
        self.dialog.geometry(f"400x200+{x}+{y}")
        
        # Content
        main_frame = ctk.CTkFrame(self.dialog)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        self.title_label = ctk.CTkLabel(main_frame, text=title, 
                                       font=ctk.CTkFont(size=16, weight="bold"))
        self.title_label.pack(pady=(10, 20))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(main_frame, width=300)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)
        
        # Status label
        self.status_label = ctk.CTkLabel(main_frame, text="Initializing...")
        self.status_label.pack(pady=10)
        
        # Focus and show
        self.dialog.focus_force()
        self.dialog.lift()
    
    def do_nothing(self):
        """Prevent dialog from being closed"""
        pass
    
    def update_progress(self, status_text, progress_percent):
        """Update progress bar and status"""
        self.status_label.configure(text=status_text)
        self.progress_bar.set(progress_percent / 100)
        self.dialog.update()
    
    def close_and_show_preview(self, book, preview_text, full_content):
        """Close dialog and show preview window"""
        self.dialog.destroy()
        self.main_app.show_preview_window(book, preview_text, full_content)
    
    def close_with_error(self, error_message):
        """Close dialog and show error"""
        self.dialog.destroy()
        messagebox.showerror("Error", error_message)

class EvenBookGUI:
    """Main GUI application for EvenBook"""
    
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("📖 EvenBook - G1 Smart Glasses Reader")
        self.root.geometry("1400x900")  # Larger default size
        
        # Start maximized and initially hide until connected
        self.root.state('zoomed')  # Windows maximized
        self.root.withdraw()  # Hide initially
        
        # Connection state
        self.is_glasses_connected = False
        
        # Initialize components
        self.api = ProjectGutenbergAPI()
        self.reader = G1Reader(on_display_update=self.update_live_preview, on_exit_callback=self.on_reading_exit)
        self.books: List[Book] = []  # Legacy - for compatibility
        self.search_books_list: List[Book] = []  # Search results
        self.popular_books: List[Book] = []  # Popular books
        self.local_books: List[Book] = []
        self.current_session: Optional[ReadingSession] = None
        
        # Live preview components
        self.live_preview_text = None
        self.live_preview_highlighted = None
        
        # Create UI
        self.setup_ui()
        
        # Load local books
        self.load_local_books()
        
        # Auto-connect to G1 glasses in background
        self.auto_connect_g1()
    
    def update_live_preview(self, display_text: str, highlighted_text: str = ""):
        """Update the live preview display with exact G1 formatting"""
        try:
            # Format text to exact G1 display specs (5 lines, 55 chars per line)
            formatted_text = self.format_for_g1_display(display_text)
            
            if self.live_preview_text:
                self.live_preview_text.delete("1.0", "end")
                self.live_preview_text.insert("1.0", formatted_text)
            
            if self.live_preview_highlighted and highlighted_text:
                formatted_highlighted = self.format_for_g1_display(highlighted_text)
                self.live_preview_highlighted.delete("1.0", "end")
                self.live_preview_highlighted.insert("1.0", formatted_highlighted)
            elif self.live_preview_highlighted:
                self.live_preview_highlighted.delete("1.0", "end")
                self.live_preview_highlighted.insert("1.0", formatted_text)
        except Exception as e:
            print(f"Error updating live preview: {e}")
    
    def format_for_g1_display(self, text: str) -> str:
        """Format text exactly as it appears on G1 display (5 lines x 55 chars)"""
        lines = text.split('\n')
        formatted_lines = []
        
        # Process up to 5 lines (G1 display limit)
        for i in range(5):
            if i < len(lines):
                line = lines[i]
                # Truncate or pad to exactly 55 characters
                if len(line) > 55:
                    line = line[:55]
                else:
                    line = line.ljust(55)  # Pad with spaces
                formatted_lines.append(line)
            else:
                # Empty line padded to 55 spaces
                formatted_lines.append(' ' * 55)
        
        return '\n'.join(formatted_lines)
    
    def setup_ui(self):
        """Set up the user interface"""
        # Create main notebook for tabs
        self.notebook = ctk.CTkTabview(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create tabs
        self.setup_browse_tab()
        self.setup_library_tab()
        self.setup_reader_tab()
        self.setup_settings_tab()
    
    def setup_browse_tab(self):
        """Set up book browsing tab with modern card layout"""
        browse_frame = self.notebook.add("🔍 Browse Books")
        
        # Header section
        header_frame = ctk.CTkFrame(browse_frame)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(header_frame, text="📚 Browse Free Books from Project Gutenberg", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # Search controls
        search_controls = ctk.CTkFrame(header_frame)
        search_controls.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(search_controls, text="Search:").grid(row=0, column=0, padx=5, pady=5)
        self.search_entry = ctk.CTkEntry(search_controls, width=300, placeholder_text="Enter book title or author...")
        self.search_entry.grid(row=0, column=1, padx=5, pady=5)
        self.search_entry.bind("<Return>", lambda e: self.search_books())  # Enter key search
        
        ctk.CTkLabel(search_controls, text="Language:").grid(row=0, column=2, padx=5, pady=5)
        self.language_combo = ctk.CTkComboBox(search_controls, values=["en", "fr", "de", "es", "it"], width=100)
        self.language_combo.set("en")
        self.language_combo.grid(row=0, column=3, padx=5, pady=5)
        
        search_btn = ctk.CTkButton(search_controls, text="🔍 Search", command=self.search_books)
        search_btn.grid(row=0, column=4, padx=5, pady=5)
        
        clear_btn = ctk.CTkButton(search_controls, text="🔄 Clear", command=self.clear_search)
        clear_btn.grid(row=0, column=5, padx=5, pady=5)
        
        # Main content area with two columns
        content_frame = ctk.CTkFrame(browse_frame)
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left column - Search Results
        search_results_frame = ctk.CTkFrame(content_frame)
        search_results_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(search_results_frame, text="🔍 Search Results", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 5))
        
        # Search results cards container
        self.search_cards_frame = ctk.CTkScrollableFrame(search_results_frame, height=400)
        self.search_cards_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Right column - Popular Books
        popular_frame = ctk.CTkFrame(content_frame)
        popular_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        ctk.CTkLabel(popular_frame, text="🏆 Top 100 Popular Books", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(10, 5))
        
        # Popular books cards container
        self.popular_cards_frame = ctk.CTkScrollableFrame(popular_frame, height=400)
        self.popular_cards_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Initialize with empty states
        self.display_books_in_grid([], self.search_cards_frame, "search", 2)  # 2 cards per row for side panels
        
        # Load popular books by default
        self.load_popular_books()
    
    def setup_library_tab(self):
        """Set up local library tab with modern card layout"""
        library_frame = self.notebook.add("📚 My Library")
        
        # Header
        header_frame = ctk.CTkFrame(library_frame)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(header_frame, text="📚 My Downloaded Books", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        # Controls
        controls_frame = ctk.CTkFrame(header_frame)
        controls_frame.pack(fill="x", padx=10, pady=10)
        
        refresh_btn = ctk.CTkButton(controls_frame, text="🔄 Refresh", command=self.load_local_books)
        refresh_btn.pack(side="left", padx=5)
        
        import_btn = ctk.CTkButton(controls_frame, text="📁 Import Text File", command=self.import_text_file)
        import_btn.pack(side="left", padx=5)
        
        delete_btn = ctk.CTkButton(controls_frame, text="🗑️ Delete Selected", command=self.delete_selected_book)
        delete_btn.pack(side="left", padx=5)
        
        # Create scrollable frame for book cards
        self.library_cards_frame = ctk.CTkScrollableFrame(library_frame, height=400)
        self.library_cards_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Store selected book
        self.selected_library_book = None
    
    def create_book_card(self, parent_frame, book, card_type="library", card_width=280, card_height=200):
        """Create a modern book card with image placeholder and theme consistency"""
        # Create card frame
        card_frame = ctk.CTkFrame(parent_frame, width=card_width, height=card_height, corner_radius=10)
        card_frame.pack_propagate(False)  # Maintain fixed size
        
        # Card content frame
        content_frame = ctk.CTkFrame(card_frame, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Top section with book image placeholder and info
        top_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        top_frame.pack(fill="x", pady=(0, 10))
        
        # Book cover placeholder (left side)
        cover_frame = ctk.CTkFrame(top_frame, width=60, height=80, corner_radius=5)
        cover_frame.pack(side="left", padx=(0, 10))
        cover_frame.pack_propagate(False)
        
        # Placeholder book image (you can replace with actual cover later)
        ctk.CTkLabel(cover_frame, text="📖", font=ctk.CTkFont(size=30)).pack(expand=True)
        
        # Book info (right side)
        info_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True)
        
        # Title (truncated if too long)
        title_text = book.title if len(book.title) <= 35 else book.title[:32] + "..."
        title_label = ctk.CTkLabel(info_frame, text=title_text, 
                                  font=ctk.CTkFont(size=14, weight="bold"),
                                  anchor="w", justify="left")
        title_label.pack(anchor="w", pady=(0, 5))
        
        # Author
        author_text = f"by {book.author}" if len(book.author) <= 30 else f"by {book.author[:27]}..."
        author_label = ctk.CTkLabel(info_frame, text=author_text,
                                   font=ctk.CTkFont(size=12),
                                   anchor="w", justify="left")
        author_label.pack(anchor="w", pady=(0, 5))
        
        # Stats row
        stats_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        stats_frame.pack(fill="x", pady=(0, 10))
        
        # Word count and reading time (if available)
        if hasattr(book, 'content') and book.content:
            word_count = len(book.content.split())
            reading_time = max(1, word_count // 200)  # Rough estimate: 200 WPM
            stats_text = f"📄 {word_count:,} words • ⏱️ ~{reading_time} min"
        else:
            stats_text = "📄 Available for download"
        
        stats_label = ctk.CTkLabel(stats_frame, text=stats_text,
                                  font=ctk.CTkFont(size=10),
                                  anchor="w")
        stats_label.pack(anchor="w")
        
        # Additional info based on card type
        if card_type == "popular" and hasattr(book, 'downloads'):
            dl_label = ctk.CTkLabel(stats_frame, text=f"⬇️ {book.downloads:,} downloads",
                                   font=ctk.CTkFont(size=10),
                                   anchor="w")
            dl_label.pack(anchor="w")
        
        # Action buttons
        button_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        button_frame.pack(fill="x", side="bottom")
        
        if card_type == "library":
            # Library book - Read button
            read_btn = ctk.CTkButton(button_frame, text="👓 Read", height=30,
                                    command=lambda: self.start_reading_book(book))
            read_btn.pack(side="left", padx=(0, 5), fill="x", expand=True)
            
            delete_btn = ctk.CTkButton(button_frame, text="🗑️", width=40, height=30,
                                      command=lambda: self.delete_book_card(book, card_frame))
            delete_btn.pack(side="right")
            
        else:
            # Popular/Search book - Preview and Download buttons
            preview_btn = ctk.CTkButton(button_frame, text="👁️ Preview", height=30,
                                       command=lambda: self.preview_book_card(book))
            preview_btn.pack(side="left", padx=(0, 5), fill="x", expand=True)
            
            download_btn = ctk.CTkButton(button_frame, text="⬇️", width=40, height=30,
                                        command=lambda: self.download_book_card(book))
            download_btn.pack(side="right")
        
        # Click to select
        def select_card():
            if card_type == "library":
                self.selected_library_book = book
            # Visual feedback could be added here
        
        card_frame.bind("<Button-1>", lambda e: select_card())
        content_frame.bind("<Button-1>", lambda e: select_card())
        
        return card_frame
    
    def preview_book_card(self, book):
        """Preview book from card"""
        # Set this book as the current selection for preview
        self.current_preview_book = book
        self.preview_book_directly(book)
    
    def preview_book_directly(self, book):
        """Preview a specific book directly with progress dialog"""
        def preview_thread():
            """Download and show preview in background thread"""
            try:
                # Create BookInfo object for our API client
                book_info = BookInfo(
                    id=int(book.id),
                    title=book.title,
                    authors=[book.author],
                    languages=[book.language],
                    subjects=[],
                    download_count=book.downloads,
                    formats={'text/plain': book.text_url}
                )
                
                # Update progress dialog
                self.root.after(0, lambda: progress_dialog.update_progress("📥 Downloading content...", 30))
                
                # Download full text
                full_content = self.api.client.download_text(book_info)
                if full_content:
                    # Update progress
                    self.root.after(0, lambda: progress_dialog.update_progress("🧹 Processing text...", 60))
                    
                    clean_content = TextProcessor.clean_text(full_content)
                    preview_text = clean_content[:2000] + "..." if len(clean_content) > 2000 else clean_content
                    
                    # Update progress
                    self.root.after(0, lambda: progress_dialog.update_progress("💾 Saving to library...", 80))
                    
                    # Auto-save to local library
                    self.auto_save_book(book, clean_content)
                    
                    # Complete and show preview
                    self.root.after(0, lambda: progress_dialog.update_progress("✅ Complete!", 100))
                    time.sleep(0.5)  # Brief pause to show completion
                    
                    # Close progress and show preview
                    self.root.after(0, lambda: progress_dialog.close_and_show_preview(book, preview_text, clean_content))
                else:
                    self.root.after(0, lambda: progress_dialog.close_with_error("Failed to download book content"))
                    
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: progress_dialog.close_with_error(f"Preview failed: {error_msg}"))
        
        # Create and show progress dialog
        progress_dialog = ProgressDialog(self.root, f"Downloading '{book.title}'", self)
        
        # Run in background thread to prevent freezing
        import threading
        threading.Thread(target=preview_thread, daemon=True).start()
    
    def download_book_card(self, book):
        """Download book from card with progress dialog"""
        self.preview_book_directly(book)  # Use the same method as preview since it auto-downloads
    
    def delete_book_card(self, book, card_frame):
        """Delete book and remove card"""
        try:
            # Delete file
            import os
            safe_filename = "".join(c for c in book.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filepath = os.path.join("books", f"{safe_filename}.json")
            
            if os.path.exists(filepath):
                os.remove(filepath)
                card_frame.destroy()
                print(f"✅ Deleted: {book.title}")
            else:
                print(f"❌ File not found: {filepath}")
        except Exception as e:
            print(f"❌ Error deleting book: {e}")
    
    def display_books_in_grid(self, books, parent_frame, card_type="library", cards_per_row=4):
        """Display books in a grid layout with 4 cards per row"""
        # Clear existing cards
        for widget in parent_frame.winfo_children():
            widget.destroy()
        
        if not books:
            no_books_label = ctk.CTkLabel(parent_frame, 
                                         text="📚 No books found" if card_type == "library" else "🔍 Search for books above",
                                         font=ctk.CTkFont(size=16))
            no_books_label.pack(pady=50)
            return
        
        # Create grid
        current_row_frame = None
        cards_in_current_row = 0
        
        for i, book in enumerate(books):
            # Create new row frame if needed
            if cards_in_current_row == 0:
                current_row_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
                current_row_frame.pack(fill="x", padx=5, pady=5)
            
            # Create book card
            card = self.create_book_card(current_row_frame, book, card_type)
            card.pack(side="left", padx=5, pady=5)
            
            cards_in_current_row += 1
            
            # Start new row after specified number of cards
            if cards_in_current_row >= cards_per_row:
                cards_in_current_row = 0
    
    def setup_reader_tab(self):
        """Set up reading control tab with live preview"""
        reader_frame = self.notebook.add("👓 G1 Reader")
        
        # Create main paned window for split layout
        main_paned = ctk.CTkFrame(reader_frame)
        main_paned.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left side - Controls
        left_frame = ctk.CTkFrame(main_paned)
        left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Connection section
        connection_frame = ctk.CTkFrame(left_frame)
        connection_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(connection_frame, text="👓 G1 Glasses Connection", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        connection_controls = ctk.CTkFrame(connection_frame)
        connection_controls.pack(fill="x", padx=10, pady=10)
        
        self.connect_btn = ctk.CTkButton(connection_controls, text="🔗 Connect to G1", 
                                        command=self.toggle_connection, width=150)
        self.connect_btn.pack(side="left", padx=5)
        
        self.connection_status = ctk.CTkLabel(connection_controls, text="🔄 Auto-connecting...")
        self.connection_status.pack(side="left", padx=10)
        
        # Connection troubleshooting
        trouble_frame = ctk.CTkFrame(connection_frame)
        trouble_frame.pack(fill="x", padx=10, pady=5)
        
        clear_config_btn = ctk.CTkButton(trouble_frame, text="🔄 Clear Saved Addresses", 
                                        command=self.clear_g1_config, width=150)
        clear_config_btn.pack(side="left", padx=5)
        
        ctk.CTkLabel(trouble_frame, text="Use if connection keeps failing").pack(side="left", padx=10)
        
        # Book info and stats
        book_frame = ctk.CTkFrame(left_frame)
        book_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(book_frame, text="📖 Current Book", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=5)
        
        self.current_book_label = ctk.CTkLabel(book_frame, text="No book selected", 
                                              font=ctk.CTkFont(size=14))
        self.current_book_label.pack(pady=5)
        
        # Book statistics
        self.book_stats_label = ctk.CTkLabel(book_frame, text="", 
                                           font=ctk.CTkFont(size=12))
        self.book_stats_label.pack(pady=2)
        
        # Reading speed control
        speed_frame = ctk.CTkFrame(left_frame)
        speed_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(speed_frame, text="Reading Speed (WPM):").pack()
        
        speed_controls = ctk.CTkFrame(speed_frame)
        speed_controls.pack(fill="x", padx=5, pady=5)
        
        self.wpm_var = tk.IntVar(value=150)
        self.wpm_slider = ctk.CTkSlider(speed_controls, from_=50, to=300, variable=self.wpm_var, 
                                       width=300, command=self.update_wpm_label)
        self.wpm_slider.pack(side="left", padx=10)
        
        self.wpm_label = ctk.CTkLabel(speed_controls, text="150 WPM")
        self.wpm_label.pack(side="left", padx=5)
        
        # Progress
        progress_frame = ctk.CTkFrame(left_frame)
        progress_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(progress_frame, text="Reading Progress:").pack()
        self.progress_bar = ctk.CTkProgressBar(progress_frame, width=400)
        self.progress_bar.pack(pady=5)
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(progress_frame, text="0% (0/0 chunks)")
        self.progress_label.pack()
        
        # Control buttons
        control_frame = ctk.CTkFrame(left_frame)
        control_frame.pack(fill="x", padx=10, pady=10)
        
        self.play_pause_btn = ctk.CTkButton(control_frame, text="▶️ Start Reading", 
                                           command=self.toggle_reading, width=120)
        self.play_pause_btn.pack(side="left", padx=5)
        
        self.stop_btn = ctk.CTkButton(control_frame, text="⏹️ Stop", 
                                     command=self.stop_reading, width=80)
        self.stop_btn.pack(side="left", padx=5)
        
        # Gesture instructions
        instructions_frame = ctk.CTkFrame(left_frame)
        instructions_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(instructions_frame, text="🎮 G1 Controls:", 
                    font=ctk.CTkFont(size=14, weight="bold")).pack()
        ctk.CTkLabel(instructions_frame, text="• Double Tap RIGHT: Start/Pause/Resume").pack()
        ctk.CTkLabel(instructions_frame, text="• Double Tap LEFT: Exit reading mode").pack()
        ctk.CTkLabel(instructions_frame, text="• 3-second countdown before reading starts").pack()
        
        # Right side - Live Preview
        right_frame = ctk.CTkFrame(main_paned)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        ctk.CTkLabel(right_frame, text="📺 Live G1 Preview", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # G1 Display simulation
        preview_container = ctk.CTkFrame(right_frame)
        preview_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # G1 Display Simulator - Exact dimensions and format
        # G1 specs: 576x136 pixels, 5 lines, ~55 chars per line
        g1_display_frame = ctk.CTkFrame(preview_container)
        g1_display_frame.pack(padx=10, pady=10)
        
        ctk.CTkLabel(g1_display_frame, text="G1 Display: 576x136px | 5 lines x 55 chars", 
                    font=ctk.CTkFont(size=10)).pack(pady=2)
        
        # Exact G1 display simulation
        self.live_preview_text = ctk.CTkTextbox(g1_display_frame, 
                                               width=575, height=136,  # Exact G1 dimensions
                                               font=ctk.CTkFont(family="Courier New", size=12),
                                               fg_color="#000000",  # Black background
                                               text_color="#00FF00",  # Green text like G1
                                               wrap="none")  # No word wrap - exact display
        self.live_preview_text.pack(pady=5)
        
        # Preview with highlighting
        highlight_label = ctk.CTkLabel(preview_container, text="Word Highlighting Preview:")
        highlight_label.pack(pady=(10, 5))
        
        self.live_preview_highlighted = ctk.CTkTextbox(preview_container, 
                                                      width=400, height=150,
                                                      font=ctk.CTkFont(family="Arial", size=12),
                                                      fg_color="#1a1a1a",
                                                      text_color="#ffffff",
                                                      wrap="word")
        self.live_preview_highlighted.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Initialize preview with placeholder
        self.update_live_preview("EvenBook Ready\n\nConnect G1 glasses and select a book to begin\n\nWaiting for connection...", "")
    
    def setup_settings_tab(self):
        """Set up settings tab"""
        settings_frame = self.notebook.add("⚙️ Settings")
        
        ctk.CTkLabel(settings_frame, text="⚙️ EvenBook Settings", 
                    font=ctk.CTkFont(size=18, weight="bold")).pack(pady=20)
        
        # Display settings
        display_frame = ctk.CTkFrame(settings_frame)
        display_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(display_frame, text="📺 Display Settings", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        # Lines per screen
        lines_frame = ctk.CTkFrame(display_frame)
        lines_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(lines_frame, text="Lines per screen:").pack(side="left", padx=5)
        self.lines_var = tk.IntVar(value=4)
        lines_slider = ctk.CTkSlider(lines_frame, from_=3, to=6, number_of_steps=4, 
                                    variable=self.lines_var, width=200)
        lines_slider.pack(side="left", padx=10)
        self.lines_label = ctk.CTkLabel(lines_frame, text="4 lines")
        self.lines_label.pack(side="left", padx=5)
        
        # Update label when slider changes
        def update_lines_label(value):
            self.lines_label.configure(text=f"{int(value)} lines")
        lines_slider.configure(command=update_lines_label)
        
        # About section
        about_frame = ctk.CTkFrame(settings_frame)
        about_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(about_frame, text="📖 About EvenBook", 
                    font=ctk.CTkFont(size=16, weight="bold")).pack(pady=10)
        
        about_text = """
EvenBook v1.0.0 - E-book Reader for G1 Smart Glasses

Features:
• Browse and download free books from Project Gutenberg
• Read books on G1 smart glasses with smooth scrolling
• Adjustable reading speed (50-300 WPM)
• Gesture controls (tap to pause, double-tap to exit)
• Local library management

Made with ❤️ for the G1 community
        """
        
        ctk.CTkLabel(about_frame, text=about_text, justify="left").pack(padx=20, pady=10)
    
    def load_popular_books(self):
        """Load popular books into the right panel with card display"""
        try:
            # Show loading message immediately
            self.show_loading_message(self.popular_cards_frame, "📚 Loading top 100 popular books...")
            
            # Load books (this will use the fallback hardcoded list)
            popular_books = self.api.search_books("", "en", limit=100)
            
            # Display results
            self.display_popular_results(popular_books)
                
        except Exception as e:
            self.show_error_message(self.popular_cards_frame, f"Error loading books: {e}")
    
    def display_popular_results(self, results):
        """Display popular books as cards"""
        self.popular_books = results
        self.display_books_in_grid(results, self.popular_cards_frame, "popular", 2)  # 2 cards per row for side panel
    
    def search_books(self):
        """Search for books using Project Gutenberg API with card display"""
        query = self.search_entry.get().strip()
        language = self.language_combo.get()
        
        def search_thread():
            """Perform search in background thread"""
            try:
                if not query:
                    self.root.after(0, lambda: self.display_books_in_grid([], self.search_cards_frame, "search", 2))
                    return
                
                # Show loading message
                self.root.after(0, lambda: self.show_loading_message(self.search_cards_frame, "🔍 Searching..."))
                
                # Search books
                search_results = self.api.search_books(query, language, limit=50)
                
                # Update UI on main thread
                self.root.after(0, lambda: self.display_search_results(search_results))
                    
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: self.show_error_message(self.search_cards_frame, f"Search error: {error_msg}"))
        
        # Run search in background thread
        import threading
        threading.Thread(target=search_thread, daemon=True).start()
    
    def display_search_results(self, results):
        """Display search results as cards"""
        self.search_books_list = results
        self.display_books_in_grid(results, self.search_cards_frame, "search", 2)  # 2 cards per row for side panel
    
    def show_loading_message(self, parent_frame, message):
        """Show loading message"""
        for widget in parent_frame.winfo_children():
            widget.destroy()
        
        loading_label = ctk.CTkLabel(parent_frame, text=message, 
                                    font=ctk.CTkFont(size=16))
        loading_label.pack(pady=50)
    
    def show_error_message(self, parent_frame, message):
        """Show error message"""
        for widget in parent_frame.winfo_children():
            widget.destroy()
        
        error_label = ctk.CTkLabel(parent_frame, text=message, 
                                  font=ctk.CTkFont(size=14),
                                  text_color="#ff6b6b")
        error_label.pack(pady=50)
    
    def clear_search(self):
        """Clear search results"""
        self.search_entry.delete(0, tk.END)
        self.display_books_in_grid([], self.search_cards_frame, "search", 2)
    
    # Removed old download_selected_book method - now using card system
    
    def download_selected_book_legacy_removed(self):
        """Download the selected book"""
        # Check which tree has a selection
        search_selection = self.search_results_tree.selection()
        popular_selection = self.popular_tree.selection()
        
        if search_selection:
            # Get book from search results
            item_index = self.search_results_tree.index(search_selection[0])
            if hasattr(self, 'search_books_list') and item_index < len(self.search_books_list):
                book = self.search_books_list[item_index]
            else:
                messagebox.showwarning("Invalid Selection", "Please search for books first.")
                return
        elif popular_selection:
            # Get book from popular books
            item_index = self.popular_tree.index(popular_selection[0])
            if hasattr(self, 'popular_books') and item_index < len(self.popular_books):
                book = self.popular_books[item_index]
            else:
                messagebox.showwarning("Invalid Selection", "Please wait for popular books to load.")
                return
        else:
            messagebox.showwarning("No Selection", "Please select a book from either search results or popular books.")
            return
        
        # Check if already downloaded
        if book.local_path and os.path.exists(book.local_path):
            messagebox.showinfo("Already Downloaded", f"'{book.title}' is already in your library.")
            return
        
        # Show downloading progress
        progress_window = ctk.CTkToplevel(self.root)
        progress_window.title("Downloading...")
        progress_window.geometry("300x100")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        ctk.CTkLabel(progress_window, text=f"Downloading '{book.title[:30]}...'").pack(pady=20)
        progress_bar = ctk.CTkProgressBar(progress_window, width=250)
        progress_bar.pack(pady=10)
        progress_bar.set(0.5)  # Indeterminate progress
        
        # Download book in a separate thread to avoid blocking UI
        def download_thread():
            try:
                success = self.api.download_book(book)
                # Update UI in main thread
                self.root.after(0, lambda: download_complete(success))
            except Exception as e:
                self.root.after(0, lambda: download_complete(False, str(e)))
        
        def download_complete(success, error=None):
            progress_window.destroy()
            if success:
                messagebox.showinfo("Download Complete", f"'{book.title}' has been downloaded to your library!")
                self.load_local_books()  # Refresh library
                # Update status in trees
                self.load_popular_books()  # Refresh popular books status
                if hasattr(self, 'search_books_list'):
                    self.search_books()  # Refresh search results status
            else:
                error_msg = f"Failed to download '{book.title}'."
                if error:
                    error_msg += f"\nError: {error}"
                messagebox.showerror("Download Failed", error_msg)
        
        # Start download
        import threading
        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()
    
    def preview_selected_book(self):
        """Preview the selected book with auto-download and no freezing"""
        # Check which tree has a selection
        search_selection = self.search_results_tree.selection()
        popular_selection = self.popular_tree.selection()
        
        if search_selection:
            # Get book from search results
            item_index = self.search_results_tree.index(search_selection[0])
            if hasattr(self, 'search_books_list') and item_index < len(self.search_books_list):
                book = self.search_books_list[item_index]
            else:
                messagebox.showwarning("Invalid Selection", "Please search for books first.")
                return
        elif popular_selection:
            # Get book from popular books
            item_index = self.popular_tree.index(popular_selection[0])
            if hasattr(self, 'popular_books') and item_index < len(self.popular_books):
                book = self.popular_books[item_index]
            else:
                messagebox.showwarning("Invalid Selection", "Please wait for popular books to load.")
                return
        else:
            messagebox.showwarning("No Selection", "Please select a book from either search results or popular books.")
            return
        
        def preview_thread():
            """Download and show preview in background thread"""
            try:
                # Create BookInfo object for our API client
                book_info = BookInfo(
                    id=int(book.id),
                    title=book.title,
                    authors=[book.author],
                    languages=[book.language],
                    subjects=[],
                    download_count=book.downloads,
                    formats={'text/plain': book.text_url}
                )
                
                # Update progress dialog
                self.root.after(0, lambda: progress_dialog.update_progress("📥 Downloading content...", 30))
                
                # Download full text
                full_content = self.api.client.download_text(book_info)
                if full_content:
                    # Update progress
                    self.root.after(0, lambda: progress_dialog.update_progress("🧹 Processing text...", 60))
                    
                    clean_content = TextProcessor.clean_text(full_content)
                    preview_text = clean_content[:2000] + "..." if len(clean_content) > 2000 else clean_content
                    
                    # Update progress
                    self.root.after(0, lambda: progress_dialog.update_progress("💾 Saving to library...", 80))
                    
                    # Auto-save to local library
                    self.auto_save_book(book, clean_content)
                    
                    # Complete and show preview
                    self.root.after(0, lambda: progress_dialog.update_progress("✅ Complete!", 100))
                    time.sleep(0.5)  # Brief pause to show completion
                    
                    # Close progress and show preview
                    self.root.after(0, lambda: progress_dialog.close_and_show_preview(book, preview_text, clean_content))
                else:
                    self.root.after(0, lambda: progress_dialog.close_with_error("Failed to download book content"))
                    
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda: progress_dialog.close_with_error(f"Preview failed: {error_msg}"))
        
        # Create and show progress dialog
        progress_dialog = ProgressDialog(self.root, f"Downloading '{book.title}'", self)
        
        # Run in background thread to prevent freezing
        import threading
        threading.Thread(target=preview_thread, daemon=True).start()
    
    def show_preview_window(self, book, preview_text: str, full_content: str):
        """Show the preview window on main thread"""
        try:
            # Create preview window
            preview_window = ctk.CTkToplevel(self.root)
            preview_window.title(f"Preview: {book.title}")
            preview_window.geometry("800x700")
            
            # Header with book info
            header_frame = ctk.CTkFrame(preview_window)
            header_frame.pack(fill="x", padx=20, pady=(20, 10))
            
            ctk.CTkLabel(header_frame, text=book.title, 
                        font=ctk.CTkFont(size=18, weight="bold")).pack(pady=5)
            ctk.CTkLabel(header_frame, text=f"by {book.author}", 
                        font=ctk.CTkFont(size=14)).pack()
            ctk.CTkLabel(header_frame, text=f"Language: {book.language.upper()} | Downloads: {book.downloads:,}", 
                        font=ctk.CTkFont(size=12)).pack()
            
            # Preview text (using CTkTextbox for better theming)
            text_widget = ctk.CTkTextbox(preview_window, wrap="word")
            text_widget.pack(fill="both", expand=True, padx=20, pady=10)
            text_widget.insert("1.0", preview_text)
            
            # Buttons
            button_frame = ctk.CTkFrame(preview_window)
            button_frame.pack(fill="x", padx=20, pady=(0, 20))
            
            ctk.CTkButton(button_frame, text="📖 Download & Read Now", 
                         command=lambda: self.download_and_read_book(book, full_content, preview_window),
                         font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="❌ Close", 
                         command=preview_window.destroy).pack(side="right", padx=5)
            
        except Exception as e:
            messagebox.showerror("Error", f"Error showing preview: {e}")
    
    def auto_save_book(self, book, content: str):
        """Automatically save book to local library"""
        try:
            book_obj = Book(
                id=book.id,
                title=book.title,
                author=book.author,
                language=book.language,
                downloads=book.downloads,
                text_url=book.text_url,
                content=content,
                source="Project Gutenberg"
            )
            
            # Save to local library
            import json
            import os
            
            books_dir = "books"
            if not os.path.exists(books_dir):
                os.makedirs(books_dir)
            
            safe_filename = "".join(c for c in book.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filepath = os.path.join(books_dir, f"{safe_filename}.json")
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'title': book_obj.title,
                    'author': book_obj.author,
                    'content': book_obj.content,
                    'source': book_obj.source
                }, f, ensure_ascii=False, indent=2)
            
            # Don't refresh here to avoid circular dependency
            print(f"✅ Book automatically saved to library: {book.title}")
            
        except Exception as e:
            print(f"❌ Error auto-saving book: {e}")
    
    def download_and_read_book(self, book, content: str, preview_window):
        """Download book and start reading immediately"""
        try:
            preview_window.destroy()
            
            book_obj = Book(
                id=book.id,
                title=book.title,
                author=book.author,
                language=book.language,
                downloads=book.downloads,
                text_url=book.text_url,
                content=content,
                source="Project Gutenberg"
            )
            
            # Switch to reader tab and start reading
            self.notebook.set("📚 Reader")
            self.start_reading_book(book_obj)
            
        except Exception as e:
            error_msg = str(e)
            messagebox.showerror("Error", f"Error starting reading: {error_msg}")
    
    def load_local_books(self):
        """Load books from local library and display as cards"""
        books_dir = "books"
        if not os.path.exists(books_dir):
            # Create empty directory and show empty state
            os.makedirs(books_dir, exist_ok=True)
            self.display_books_in_grid([], self.library_cards_frame, "library")
            return
        
        self.local_books = []
        
        # Load JSON book files (new format) and legacy TXT files
        for filename in os.listdir(books_dir):
            filepath = os.path.join(books_dir, filename)
            
            try:
                if filename.endswith('.json'):
                    # New JSON format
                    with open(filepath, 'r', encoding='utf-8') as f:
                        book_data = json.load(f)
                    
                    book = Book(
                        id=book_data.get('id', 'unknown'),
                        title=book_data.get('title', 'Unknown Title'),
                        author=book_data.get('author', 'Unknown Author'),
                        language=book_data.get('language', 'en'),
                        downloads=book_data.get('downloads', 0),
                        text_url=book_data.get('text_url', ''),
                        content=book_data.get('content', ''),
                        source=book_data.get('source', 'Local'),
                        local_path=filepath
                    )
                    
                elif filename.endswith('.txt'):
                    # Legacy TXT format - migrate to JSON
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Parse filename to extract book info
                    parts = filename.replace('.txt', '').split('_')
                    if len(parts) >= 3:
                        book_id = parts[0]
                        title = ' '.join(parts[1:-1]).replace('-', ' ')
                        author = parts[-1].replace('-', ' ')
                    else:
                        book_id = "unknown"
                        title = filename.replace('.txt', '').replace('_', ' ')
                        author = "Unknown Author"
                    
                    book = Book(
                        id=book_id,
                        title=title,
                        author=author,
                        language="en",
                        downloads=0,
                        text_url="",
                        content=content,
                        source="Local Import",
                        local_path=filepath
                    )
                    
                    # Note: TXT files can be used directly, migration to JSON happens on first edit/download
                    
                else:
                    continue  # Skip non-book files
                
                self.local_books.append(book)
                
            except Exception as e:
                print(f"❌ Error loading book {filename}: {e}")
        
        # Display books as cards
        self.display_books_in_grid(self.local_books, self.library_cards_frame, "library")
    
    def import_text_file(self):
        """Import a text file as a book"""
        filetypes = [("Text files", "*.txt"), ("All files", "*.*")]
        filepath = filedialog.askopenfilename(title="Select Text File", filetypes=filetypes)
        
        if not filepath:
            return
        
        # Copy to books directory
        books_dir = "books"
        os.makedirs(books_dir, exist_ok=True)
        
        filename = os.path.basename(filepath)
        dest_path = os.path.join(books_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as src:
                content = src.read()
            with open(dest_path, 'w', encoding='utf-8') as dst:
                dst.write(content)
            
            messagebox.showinfo("Import Complete", f"'{filename}' has been added to your library!")
            self.load_local_books()
            
        except Exception as e:
            messagebox.showerror("Import Failed", f"Failed to import file: {e}")
    
    def delete_selected_book(self):
        """Delete the selected book from library"""
        selection = self.library_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a book to delete.")
            return
        
        item_index = self.library_tree.index(selection[0])
        book = self.local_books[item_index]
        
        # Confirm deletion
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{book.title}'?"):
            try:
                os.remove(book.local_path)
                messagebox.showinfo("Deleted", f"'{book.title}' has been removed from your library.")
                self.load_local_books()
            except Exception as e:
                messagebox.showerror("Delete Failed", f"Failed to delete book: {e}")
    
    def start_reading_selected(self):
        """Start reading the selected book"""
        selection = self.library_tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a book to read.")
            return
        
        item_index = self.library_tree.index(selection[0])
        book = self.local_books[item_index]
        
        # Create reading session
        self.current_session = ReadingSession(
            book=book,
            words_per_minute=self.wpm_var.get(),
            lines_per_screen=self.lines_var.get()
        )
        
        # Update UI
        self.current_book_label.configure(text=f"📖 {book.title}")
        self.notebook.set("👓 G1 Reader")  # Switch to reader tab
        
        # Check G1 connection
        if not self.reader.is_connected:
            if messagebox.askyesno("Connect G1", 
                                 "G1 glasses not connected. Would you like to connect now?"):
                self.toggle_connection()
    
    def start_reading_book(self, book: Book):
        """Start reading a specific book directly"""
        try:
            # Create reading session
            self.current_session = ReadingSession(
                book=book,
                words_per_minute=self.wpm_var.get(),
                lines_per_screen=self.lines_var.get()
            )
            
            # Update UI
            self.current_book_label.configure(text=f"📖 {book.title}")
            self.notebook.set("📚 Reader")  # Switch to reader tab
            
            # Check G1 connection
            if not self.reader.is_connected:
                if messagebox.askyesno("Connect G1", 
                                     "G1 glasses not connected. Would you like to connect now?"):
                    self.toggle_connection()
                else:
                    messagebox.showinfo("Info", "Book loaded. Connect G1 glasses to start reading.")
            else:
                # Set up session and wait for gesture to start
                self.reader.start_reading_sync(self.current_session, self.update_progress)
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start reading: {e}")
    
    def on_reading_exit(self):
        """Handle reading exit from double tap gesture"""
        try:
            # Update button states
            self.play_pause_btn.configure(text="▶️ Start Reading")
            self.progress_bar.set(0)
            self.progress_label.configure(text="Reading stopped")
            
            # Clear current session
            self.current_session = None
            self.current_book_label.configure(text="📖 No book selected")
            
            print("📖 Reading stopped by gesture")
        except Exception as e:
            print(f"Error handling reading exit: {e}")
    
    def toggle_reading(self):
        """Toggle reading state - Start/Pause/Resume"""
        try:
            if not self.current_session:
                messagebox.showwarning("No Book", "Please select a book first.")
                return
            
            if not self.reader.is_connected:
                if messagebox.askyesno("Connect G1", "G1 glasses not connected. Connect now?"):
                    self.toggle_connection()
                return
            
            # Check current state and toggle
            if not self.reader.is_reading:
                # Start reading
                self.reader.start_reading_sync(self.current_session, self.update_progress)
                self.play_pause_btn.configure(text="⏸️ Pause")
            else:
                if self.current_session.is_paused:
                    # Resume reading
                    self.current_session.is_paused = False
                    self.current_session.reading_state = "reading"
                    self.play_pause_btn.configure(text="⏸️ Pause")
                else:
                    # Pause reading
                    self.current_session.is_paused = True
                    self.current_session.reading_state = "paused"
                    self.play_pause_btn.configure(text="▶️ Resume")
        
        except Exception as e:
            messagebox.showerror("Error", f"Failed to toggle reading: {e}")
    
    def stop_reading(self):
        """Stop reading completely"""
        try:
            if self.reader.is_reading:
                self.reader.stop_reading()
            
            # Update GUI state
            self.on_reading_exit()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop reading: {e}")
    
    def update_wpm_label(self, value):
        """Update WPM label when slider changes"""
        self.wpm_label.configure(text=f"{int(value)} WPM")
    
    def clear_g1_config(self):
        """Clear saved G1 addresses and force fresh scan"""
        try:
            if messagebox.askyesno("Clear G1 Config", 
                                 "This will disconnect G1 glasses from Windows and clear saved addresses. Continue?"):
                
                # First disconnect if currently connected
                if self.reader.is_connected:
                    self.reader.disconnect_sync()
                
                # Force disconnect from Windows Bluetooth
                try:
                    import subprocess
                    self.connection_status.configure(text="🔄 Disconnecting from Windows...")
                    self.root.update()
                    
                    result = subprocess.run(
                        'powershell -Command "Get-PnpDevice | Where-Object {$_.Name -like \'*G1*\' -and $_.Status -eq \'OK\'} | Disable-PnpDevice -Confirm:$false"',
                        shell=True, capture_output=True, text=True
                    )
                    print("Disconnected G1 devices from Windows")
                except Exception as e:
                    print(f"Could not force disconnect: {e}")
                
                # Clear the config
                if hasattr(self.reader, 'glasses') and hasattr(self.reader.glasses, 'config'):
                    self.reader.glasses.config.left_address = None
                    self.reader.glasses.config.right_address = None
                    self.reader.glasses.config.save()
                
                # Also clear the config file directly
                import os
                config_file = os.path.join(os.getcwd(), "g1_config.json")
                if os.path.exists(config_file):
                    os.remove(config_file)
                
                messagebox.showinfo("Config Cleared", 
                                  "G1 configuration cleared and devices disconnected from Windows.\n\n" +
                                  "Now try connecting again - it should perform a fresh scan.")
                self.connection_status.configure(text="❌ Config Cleared - Ready for Fresh Connection")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear config: {e}")
    
    def auto_connect_g1(self):
        """Auto-connect to G1 glasses in background"""
        def connect_background():
            try:
                connected = self.reader.connect_sync()
                # Update UI in main thread
                self.root.after(0, lambda: self.update_connection_ui(connected, auto=True))
            except Exception as e:
                error_str = str(e)
                self.root.after(0, lambda: self.update_connection_ui(False, auto=True, error=error_str))
        
        # Start connection in background thread
        import threading
        thread = threading.Thread(target=connect_background, daemon=True)
        thread.start()
    
    def update_connection_ui(self, connected: bool, auto: bool = False, error: Optional[str] = None):
        """Update connection UI based on connection status"""
        if connected:
            self.is_glasses_connected = True
            
            # Show the app window when connected
            if self.root.state() == 'withdrawn':
                self.root.deiconify()  # Show the window
                self.root.lift()  # Bring to front
                self.root.focus_force()  # Give focus
            
            self.connect_btn.configure(text="🔌 Disconnect")
            # Check if we have specific connection info
            if hasattr(self.reader, 'glasses') and self.reader.glasses:
                left_connected = hasattr(self.reader.glasses, 'left_client') and self.reader.glasses.left_client and self.reader.glasses.left_client.is_connected
                right_connected = hasattr(self.reader.glasses, 'right_client') and self.reader.glasses.right_client and self.reader.glasses.right_client.is_connected
                
                if left_connected and right_connected:
                    self.connection_status.configure(text="✅ Both Glasses Connected")
                elif left_connected:
                    self.connection_status.configure(text="⚠️ Left Glass Connected")
                elif right_connected:
                    self.connection_status.configure(text="⚠️ Right Glass Connected")
                else:
                    self.connection_status.configure(text="✅ Connected")
            else:
                self.connection_status.configure(text="✅ Connected")
                
            if not auto:  # Only show success message for manual connections
                messagebox.showinfo("Connected", "Successfully connected to G1 glasses!")
        else:
            self.is_glasses_connected = False
            self.connect_btn.configure(text="🔗 Connect to G1")
            if error:
                if "not ready" in error.lower() or "not found" in error.lower():
                    self.connection_status.configure(text="❌ Glasses Not Found")
                elif "timeout" in error.lower():
                    self.connection_status.configure(text="❌ Connection Timeout")
                else:
                    self.connection_status.configure(text="❌ Connection Error")
            else:
                self.connection_status.configure(text="❌ Connection Failed")
            
            # Only show error for manual connections, and make it less intrusive for auto-connect
            if not auto and error:
                messagebox.showerror("Connection Failed", 
                                   f"Failed to connect to G1 glasses.\nError: {error}\n\nTroubleshooting:\n• Make sure glasses are powered on\n• Check Bluetooth is enabled\n• Try moving closer to glasses\n• Try re-pairing in Windows Bluetooth settings")
    
    def toggle_connection(self):
        """Toggle G1 connection with threading"""
        if self.reader.is_connected:
            # Disconnect
            def disconnect_background():
                try:
                    self.reader.disconnect_sync()
                    self.root.after(0, lambda: self.update_connection_ui(False))
                except Exception as e:
                    error_str = str(e)
                    self.root.after(0, lambda: self.update_connection_ui(False, error=error_str))
            
            import threading
            thread = threading.Thread(target=disconnect_background, daemon=True)
            thread.start()
        else:
            # Connect
            self.connect_btn.configure(text="⏳ Connecting...")
            self.connection_status.configure(text="🔄 Connecting...")
            self.root.update()
            
            def connect_background():
                try:
                    connected = self.reader.connect_sync()
                    self.root.after(0, lambda: self.update_connection_ui(connected))
                except Exception as e:
                    error_str = str(e)
                    self.root.after(0, lambda: self.update_connection_ui(False, error=error_str))
            
            import threading
            thread = threading.Thread(target=connect_background, daemon=True)
            thread.start()
    
    def toggle_reading(self):
        """Start or pause reading"""
        if not self.current_session:
            messagebox.showwarning("No Book", "Please select a book from your library first.")
            return
        
        if not self.reader.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to G1 glasses first.")
            return
        
        if not self.reader.is_reading:
            # Start reading
            self.current_session.words_per_minute = self.wpm_var.get()
            self.current_session.lines_per_screen = self.lines_var.get()
            
            self.reader.start_reading_sync(self.current_session, self.update_progress)
            self.play_pause_btn.configure(text="⏸️ Pause")
        else:
            # Pause/resume
            self.reader.pause_reading()
            if self.current_session.is_paused:
                self.play_pause_btn.configure(text="▶️ Resume")
            else:
                self.play_pause_btn.configure(text="⏸️ Pause")
    
    def stop_reading(self):
        """Stop reading"""
        self.reader.stop_reading()
        self.play_pause_btn.configure(text="▶️ Start Reading")
        self.progress_bar.set(0)
        self.progress_label.configure(text="0% (0/0 chunks)")
    
    def update_progress(self, progress: float, current: int, total: int, stats: Optional[dict] = None):
        """Update reading progress with book statistics"""
        self.progress_bar.set(progress / 100)
        self.progress_label.configure(text=f"{progress:.1f}% ({current}/{total} chunks)")
        
        # Update book statistics if provided
        if stats and self.book_stats_label:
            total_words = stats.get('total_words', 0)
            estimated_time = stats.get('estimated_time', 0)
            wpm = stats.get('words_per_minute', 150)
            
            # Calculate reading time based on progress
            time_elapsed = (progress / 100) * estimated_time
            time_remaining = estimated_time - time_elapsed
            
            stats_text = f"Words: {total_words:,} | Speed: {wpm} WPM | Time: {time_elapsed:.1f}m / {estimated_time:.1f}m | Remaining: {time_remaining:.1f}m"
            self.book_stats_label.configure(text=stats_text)
        
        # Update library tree
        if hasattr(self, 'library_tree'):
            selected = self.library_tree.selection()
            if selected:
                item = selected[0]
                values = list(self.library_tree.item(item)['values'])
                values[4] = f"{progress:.1f}%"  # Progress column
                self.library_tree.item(item, values=values)
    
    def update_wpm_label(self, value):
        """Update WPM label when slider changes"""
        self.wpm_label.configure(text=f"{int(value)} WPM")
    
    def run(self):
        """Run the application"""
        try:
            self.root.mainloop()
        finally:
            # Thorough cleanup to prevent sticky connections
            self.cleanup_on_exit()
    
    def cleanup_on_exit(self):
        """Ensure thorough cleanup on application exit"""
        try:
            print("🔄 Cleaning up connections...")
            
            # Disconnect from G1 if connected
            if self.reader.is_connected:
                self.reader.disconnect_sync()
            
            # Force disconnect any remaining BLE connections
            try:
                import subprocess
                # Use Windows command to disconnect any G1 devices
                result = subprocess.run(
                    'powershell -Command "Get-PnpDevice | Where-Object {$_.Name -like \'*G1*\' -and $_.Status -eq \'OK\'} | Disable-PnpDevice -Confirm:$false"',
                    shell=True, capture_output=True, text=True
                )
                if result.stdout:
                    print("🔌 Disconnected remaining G1 devices from Windows")
            except Exception as e:
                print(f"⚠️ Could not force disconnect devices: {e}")
            
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"❌ Error during cleanup: {e}")

def main():
    """Main entry point"""
    print("🚀 Starting EvenBook...")
    
    # Create and run the application
    app = EvenBookGUI()
    app.run()

if __name__ == "__main__":
    main()