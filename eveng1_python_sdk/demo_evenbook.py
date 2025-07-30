#!/usr/bin/env python3
"""
EvenBook Demo Script
===================

This script demonstrates all the new features implemented in EvenBook:

1. ✅ Gesture Control: Left click to start/pause/resume reading
2. ✅ Auto-scrolling: Based on user's WPM setting
3. ✅ Word Highlighting: Progressive word-by-word highlighting
4. ✅ Live Preview: Shows exactly what user sees on glasses
5. ✅ Book Statistics: Total slides, reading time, word count
6. ✅ Startup Optimization: Maximized window, hide until connected
7. ✅ Robust Reading: Proper state management and error handling

Usage:
    cd eveng1_python_sdk
    poetry run python demo_evenbook.py

Features to Test:
================

1. **Connection Flow:**
   - App starts hidden and maximized
   - Auto-connects to G1 glasses
   - Shows app window when connected

2. **Book Selection:**
   - Browse popular books (right panel)
   - Search for books (left panel)
   - Download and preview books

3. **Reading Experience:**
   - Select a book and click "Read on G1 Glasses"
   - View live preview on right side of Reader tab
   - See book statistics (word count, estimated time)
   - Use gesture controls:
     * Single tap LEFT: Start reading (shows 3-sec countdown)
     * Single tap LEFT while reading: Pause
     * Single tap LEFT while paused: Resume
     * Double tap: Exit reading

4. **Live Features:**
   - Watch word-by-word highlighting in preview
   - Adjust WPM slider to change reading speed
   - Monitor progress with detailed statistics

5. **Error Handling:**
   - Robust connection management
   - Clear troubleshooting instructions
   - Graceful error recovery

Gesture Controls:
================
- **First tap**: Shows 3-second countdown, then starts reading
- **While reading**: Single tap pauses
- **While paused**: Single tap resumes
- **Double tap**: Exits reading mode

Live Preview:
============
- **Top panel**: Green-on-black display (simulates G1 glasses)
- **Bottom panel**: Word highlighting preview with brackets [word]
- **Real-time updates**: Exactly what user sees on glasses

Book Statistics:
===============
- Total word count
- Estimated reading time
- Current WPM setting
- Time elapsed / remaining
- Progress percentage

Technical Features:
==================
- **Threaded connections**: No GUI freezing
- **Event-driven architecture**: Responsive gesture handling
- **State management**: Robust reading states (waiting, countdown, reading, paused)
- **Error resilience**: Graceful handling of connection issues
- **Memory efficient**: Chunked text processing
"""

if __name__ == "__main__":
    import sys
    import os
    
    # Add current directory to path
    sys.path.insert(0, os.getcwd())
    
    try:
        from evenbook import EvenBookGUI
        
        print("🚀 Starting EvenBook Demo...")
        print("📖 EvenBook - Advanced E-book Reader for G1 Smart Glasses")
        print("=" * 60)
        print(__doc__)
        
        # Create and run the application
        app = EvenBookGUI()
        app.run()
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Make sure you're in the eveng1_python_sdk directory and have installed dependencies")
        print("Run: poetry install")
    except Exception as e:
        print(f"❌ Error starting EvenBook: {e}")
        import traceback
        traceback.print_exc()