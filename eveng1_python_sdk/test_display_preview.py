#!/usr/bin/env python3
"""
G1 Display Preview Test
======================

This script tests the exact G1 display preview functionality.
Shows exactly what text looks like on G1 glasses with precise formatting.

Usage:
    cd eveng1_python_sdk
    poetry run python test_display_preview.py
"""

import tkinter as tk
import customtkinter as ctk

class G1DisplayPreview:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("G1 Display Preview Test")
        self.root.geometry("800x600")
        
        # Test text samples
        self.test_texts = [
            "EVENBOOK: Pride and Prejudice\n\nTotal: 1245 slides\nEst. time: 45.2 min\n\nSingle tap LEFT to start",
            "STARTING IN\n\n3",
            "STARTING IN\n\n2", 
            "STARTING IN\n\n1",
            "It is a truth universally acknowledged that a single man in possession of a good fortune must be in want of a wife.",
            "PAUSED\n\nSingle tap to resume",
            "Book completed!\n\nDouble-tap to exit"
        ]
        
        self.current_text_index = 0
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the preview UI"""
        # Header
        ctk.CTkLabel(self.root, text="G1 Display Preview Test", 
                    font=ctk.CTkFont(size=20, weight="bold")).pack(pady=10)
        
        # G1 Display specs info
        ctk.CTkLabel(self.root, text="G1 Specs: 576x136 pixels | 5 lines x 55 characters max", 
                    font=ctk.CTkFont(size=12)).pack(pady=5)
        
        # G1 Display Simulator Frame
        display_frame = ctk.CTkFrame(self.root)
        display_frame.pack(padx=20, pady=20)
        
        # Display label
        ctk.CTkLabel(display_frame, text="Exact G1 Display Simulation", 
                    font=ctk.CTkFont(size=14, weight="bold")).pack(pady=5)
        
        # Character grid info
        ctk.CTkLabel(display_frame, text="Each line shows exactly 55 characters (padded with spaces)", 
                    font=ctk.CTkFont(size=10)).pack(pady=2)
        
        # The exact G1 display
        self.display_text = ctk.CTkTextbox(display_frame,
                                          width=575, height=136,  # Exact G1 dimensions
                                          font=ctk.CTkFont(family="Courier New", size=12),
                                          fg_color="#000000",  # Black background
                                          text_color="#00FF00",  # Green text like G1
                                          wrap="none")  # No word wrap
        self.display_text.pack(pady=10)
        
        # Controls
        control_frame = ctk.CTkFrame(self.root)
        control_frame.pack(pady=10)
        
        ctk.CTkButton(control_frame, text="◀ Previous Text", 
                     command=self.previous_text, width=120).pack(side="left", padx=5)
        
        ctk.CTkButton(control_frame, text="Next Text ▶", 
                     command=self.next_text, width=120).pack(side="left", padx=5)
        
        # Current text info
        self.text_info = ctk.CTkLabel(self.root, text="", 
                                     font=ctk.CTkFont(size=10))
        self.text_info.pack(pady=5)
        
        # Show first text
        self.update_display()
        
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
    
    def update_display(self):
        """Update the display with current test text"""
        current_text = self.test_texts[self.current_text_index]
        formatted_text = self.format_for_g1_display(current_text)
        
        # Update display
        self.display_text.delete("1.0", "end")
        self.display_text.insert("1.0", formatted_text)
        
        # Update info
        lines = current_text.split('\n')
        line_count = len(lines)
        max_line_length = max(len(line) for line in lines) if lines else 0
        
        info_text = f"Text {self.current_text_index + 1}/{len(self.test_texts)} | "
        info_text += f"Lines: {line_count}/5 | Max line length: {max_line_length}/55 chars"
        
        if max_line_length > 55:
            info_text += " (TRUNCATED!)"
        
        self.text_info.configure(text=info_text)
        
        # Show raw text in console for debugging
        print(f"\n--- Test Text {self.current_text_index + 1} ---")
        print(f"Raw text: {repr(current_text)}")
        print(f"Formatted for G1:")
        for i, line in enumerate(formatted_text.split('\n')):
            print(f"Line {i+1}: '{line}' ({len(line)} chars)")
        print("-" * 60)
        
    def next_text(self):
        """Show next test text"""
        self.current_text_index = (self.current_text_index + 1) % len(self.test_texts)
        self.update_display()
        
    def previous_text(self):
        """Show previous test text"""
        self.current_text_index = (self.current_text_index - 1) % len(self.test_texts)
        self.update_display()
        
    def run(self):
        """Run the preview test"""
        print("🎯 G1 Display Preview Test")
        print("=" * 40)
        print("This shows exactly how text appears on G1 glasses.")
        print("Use Next/Previous buttons to cycle through test texts.")
        print("Check the console for detailed formatting info.")
        print("\nG1 Display Specs:")
        print("- Resolution: 576x136 pixels")
        print("- Text: 5 lines maximum")
        print("- Characters: 55 per line maximum")
        print("- Font: Monospace (Courier New simulation)")
        print("=" * 40)
        
        self.root.mainloop()

if __name__ == "__main__":
    preview = G1DisplayPreview()
    preview.run()