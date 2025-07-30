#!/usr/bin/env python3
"""
G1 Gesture Detection Debug Script
=================================

This script tests all G1 gesture detection:
- Single tap (left/right)
- Double tap (left/right) 
- Slide up/down (left/right)

Usage:
    cd eveng1_python_sdk
    poetry run python debug_gestures.py

Then perform gestures on your G1 glasses and watch the console output.
"""

import asyncio
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.getcwd())

from connector import G1Connector
from utils.logger import setup_logger
from utils.constants import StateEvent, EventCategories

class GestureDebugger:
    def __init__(self):
        self.glasses = None
        self.logger = setup_logger()
        self.gesture_counts = {
            'left_single': 0,
            'left_double': 0,
            'left_slide_up': 0,
            'left_slide_down': 0,
            'right_single': 0,
            'right_double': 0,
            'right_slide_up': 0,
            'right_slide_down': 0,
        }
        
    async def connect(self):
        """Connect to G1 glasses"""
        print("🔄 Connecting to G1 glasses...")
        self.glasses = G1Connector()
        
        connected = await self.glasses.connect()
        if connected:
            print("✅ Connected to G1 glasses!")
            print("📱 Setting up gesture detection...")
            await self.setup_gesture_detection()
            return True
        else:
            print("❌ Failed to connect to G1 glasses")
            return False
    
    async def setup_gesture_detection(self):
        """Setup gesture event detection using the same method as the SDK examples"""
        try:
            # Method 1: Try event_service if available
            if hasattr(self.glasses, 'event_service') and self.glasses.event_service:
                print("🎮 Using event_service for gesture detection...")
                # Subscribe to all interaction events (0xF5 is the state event category)
                self.glasses.event_service.subscribe_raw(EventCategories.STATE, self.handle_state_event)
                print("✅ Event service gesture detection setup complete")
            
            # Method 2: Try state_manager callback (like in examples/interactions.py)
            if hasattr(self.glasses, 'state_manager') and self.glasses.state_manager:
                print("🎮 Using state_manager for gesture detection...")
                self.glasses.state_manager.add_raw_state_callback(self.handle_raw_state)
                print("✅ State manager gesture detection setup complete")
            
            # Method 3: Try UART service direct callback (fallback)
            if hasattr(self.glasses, 'uart_service') and self.glasses.uart_service:
                print("🎮 Using UART service for gesture detection...")
                self.glasses.uart_service.add_notification_callback(self.handle_uart_notification)
                print("✅ UART service gesture detection setup complete")
                
            print("\n🎯 Gesture detection is active!")
            print("👆 Try these gestures on your G1 glasses:")
            print("   • Single tap LEFT")
            print("   • Single tap RIGHT") 
            print("   • Double tap LEFT")
            print("   • Double tap RIGHT")
            print("   🎯 EvenBook Controls:")
            print("     → Double tap RIGHT: Play/Pause")
            print("     → Double tap LEFT: Exit")
            print("   • Slide up LEFT")
            print("   • Slide down LEFT")
            print("   • Slide up RIGHT")
            print("   • Slide down RIGHT")
            print("\n📊 Gesture counts will appear below...\n")
            
        except Exception as e:
            print(f"❌ Error setting up gesture detection: {e}")
            import traceback
            traceback.print_exc()
    
    async def handle_state_event(self, raw_data: bytes, side: str):
        """Handle state events from event_service"""
        await self.process_gesture_data(raw_data, side, "event_service")
    
    async def handle_raw_state(self, raw_data: bytes, side: str):
        """Handle state events from state_manager"""
        await self.process_gesture_data(raw_data, side, "state_manager")
    
    async def handle_uart_notification(self, raw_data: bytes, side: str):
        """Handle UART notifications directly"""
        await self.process_gesture_data(raw_data, side, "uart_service")
    
    async def process_gesture_data(self, raw_data: bytes, side: str, source: str):
        """Process gesture data and identify the gesture type"""
        if not raw_data or len(raw_data) < 2:
            return
            
        try:
            category_byte = raw_data[0]
            event_code = raw_data[1] if len(raw_data) > 1 else 0
            
            # Only process state events (0xF5) which contain interaction data
            if category_byte == EventCategories.STATE:  # 0xF5
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                
                # Get interaction type
                interaction_name, interaction_label = StateEvent.get_interaction(event_code)
                
                # Map to our gesture types
                gesture_key = None
                gesture_name = "Unknown"
                
                if interaction_name == "SINGLE_TAP":
                    gesture_key = f"{side}_single"
                    gesture_name = f"Single Tap {side.upper()}"
                elif interaction_name == "DOUBLE_TAP":
                    gesture_key = f"{side}_double" 
                    gesture_name = f"Double Tap {side.upper()}"
                elif event_code == 0x06:  # Slide up (not in constants but observed)
                    gesture_key = f"{side}_slide_up"
                    gesture_name = f"Slide Up {side.upper()}"
                elif event_code == 0x07:  # Slide down (not in constants but observed)
                    gesture_key = f"{side}_slide_down"
                    gesture_name = f"Slide Down {side.upper()}"
                
                if gesture_key:
                    self.gesture_counts[gesture_key] += 1
                    print(f"🎯 [{timestamp}] {gesture_name} detected! (#{self.gesture_counts[gesture_key]}) [via {source}]")
                    print(f"   Raw data: {raw_data.hex()}")
                    self.print_gesture_summary()
                else:
                    # Log unknown gestures for debugging
                    print(f"❓ [{timestamp}] Unknown gesture from {side}: 0x{event_code:02x} [via {source}]")
                    print(f"   Raw data: {raw_data.hex()}")
                    print(f"   Interaction: {interaction_name} - {interaction_label}")
                    
        except Exception as e:
            print(f"❌ Error processing gesture data: {e}")
            print(f"   Raw data: {raw_data.hex() if raw_data else 'None'}")
    
    def print_gesture_summary(self):
        """Print current gesture count summary"""
        print("📊 Current gesture counts:")
        print(f"   Left:  Single={self.gesture_counts['left_single']} | Double={self.gesture_counts['left_double']} | Up={self.gesture_counts['left_slide_up']} | Down={self.gesture_counts['left_slide_down']}")
        print(f"   Right: Single={self.gesture_counts['right_single']} | Double={self.gesture_counts['right_double']} | Up={self.gesture_counts['right_slide_up']} | Down={self.gesture_counts['right_slide_down']}")
        print()

async def main():
    print("🎮 G1 Gesture Detection Debug Tool")
    print("==================================")
    
    debugger = GestureDebugger()
    
    # Connect to glasses
    if not await debugger.connect():
        print("❌ Cannot continue without G1 connection")
        return
    
    print("🔄 Listening for gestures... (Press Ctrl+C to stop)")
    
    try:
        # Keep the script running to listen for gestures
        while True:
            await asyncio.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping gesture detection...")
        
        # Print final summary
        print("\n📊 Final Gesture Summary:")
        print("========================")
        total_gestures = sum(debugger.gesture_counts.values())
        print(f"Total gestures detected: {total_gestures}")
        
        if total_gestures > 0:
            for gesture_type, count in debugger.gesture_counts.items():
                if count > 0:
                    percentage = (count / total_gestures) * 100
                    print(f"{gesture_type.replace('_', ' ').title()}: {count} ({percentage:.1f}%)")
        else:
            print("❌ No gestures were detected!")
            print("\nTroubleshooting:")
            print("1. Make sure G1 glasses are properly connected")
            print("2. Try touching the glasses firmly")
            print("3. Make sure you're touching the correct areas")
            print("4. Check if glasses are in the right mode")
        
    finally:
        # Clean up
        if debugger.glasses:
            print("🧹 Disconnecting from G1 glasses...")
            await debugger.glasses.disconnect()
        print("✅ Debug session completed")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()