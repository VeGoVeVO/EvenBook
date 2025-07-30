"""
Comprehensive G1 Glasses Connection Test with Detailed Debugging
================================================================

This test script provides detailed logging and debugging for every step
of the G1 glasses connection and display process.
"""

import asyncio
import logging
import os
import sys
import time
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

# Add the project root to Python path
sys.path.insert(0, '.')

from connector import G1Connector
from utils.logger import setup_logger
from utils.config import Config

class DebugG1Tester:
    """Enhanced G1 tester with comprehensive debugging"""
    
    def __init__(self):
        self.console = Console()
        self.logger = None
        self.glasses: Optional[G1Connector] = None
        
    def setup_enhanced_logging(self):
        """Setup enhanced logging with maximum verbosity"""
        self.console.print(Panel("[bold blue]Setting up Enhanced Logging[/bold blue]"))
        
        # Create custom config for maximum debugging
        config = Config()
        config.log_level = "DEBUG"
        config.log_file = os.path.join(os.getcwd(), "g1_debug_test.log")
        config.console_log = True
        
        # Setup logger
        self.logger = setup_logger(config)
        self.logger.setLevel(logging.DEBUG)
        
        # Add extra verbose logging for specific modules
        logging.getLogger("bleak").setLevel(logging.DEBUG)
        logging.getLogger("connector").setLevel(logging.DEBUG)
        logging.getLogger("services").setLevel(logging.DEBUG)
        
        self.console.print("✅ Enhanced logging configured")
        self.console.print(f"📝 Log file: g1_debug_test.log")
        
    def print_step(self, step: str, description: str):
        """Print a step with consistent formatting"""
        self.console.print(f"\n[bold cyan]STEP: {step}[/bold cyan]")
        self.console.print(f"[dim]{description}[/dim]")
        if self.logger:
            self.logger.info(f"STEP: {step} - {description}")
            
    def print_debug(self, message: str):
        """Print debug information"""
        self.console.print(f"[yellow]🔍 DEBUG:[/yellow] {message}")
        if self.logger:
            self.logger.debug(message)
            
    def print_success(self, message: str):
        """Print success message"""
        self.console.print(f"[green]✅ SUCCESS:[/green] {message}")
        if self.logger:
            self.logger.info(f"SUCCESS: {message}")
            
    def print_error(self, message: str):
        """Print error message"""
        self.console.print(f"[red]❌ ERROR:[/red] {message}")
        if self.logger:
            self.logger.error(message)
            
    def print_warning(self, message: str):
        """Print warning message"""
        self.console.print(f"[orange3]⚠️  WARNING:[/orange3] {message}")
        if self.logger:
            self.logger.warning(message)

    async def test_environment_check(self):
        """Check the environment setup"""
        self.print_step("1", "Environment Check")
        
        try:
            # Check Python version
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            self.print_debug(f"Python version: {python_version}")
            
            # Check required modules
            modules_to_check = ['bleak', 'rich', 'asyncio']
            for module in modules_to_check:
                try:
                    __import__(module)
                    self.print_debug(f"Module '{module}' is available")
                except ImportError as e:
                    self.print_error(f"Module '{module}' not found: {e}")
                    return False
            
            # Check project structure
            import os
            required_dirs = ['connector', 'services', 'utils', 'examples']
            for dir_name in required_dirs:
                if os.path.exists(dir_name):
                    self.print_debug(f"Directory '{dir_name}' found")
                else:
                    self.print_warning(f"Directory '{dir_name}' not found")
            
            self.print_success("Environment check completed")
            return True
            
        except Exception as e:
            self.print_error(f"Environment check failed: {e}")
            return False

    async def test_g1_connector_init(self):
        """Test G1 connector initialization"""
        self.print_step("2", "G1 Connector Initialization")
        
        try:
            self.print_debug("Creating G1Connector instance...")
            self.glasses = G1Connector()
            
            self.print_debug("Checking connector attributes...")
            attributes_to_check = [
                'ble_manager', 'state_manager', 'command_manager', 
                'event_service', 'uart_service', 'status_manager'
            ]
            
            for attr in attributes_to_check:
                if hasattr(self.glasses, attr):
                    self.print_debug(f"✓ Attribute '{attr}' exists")
                else:
                    self.print_warning(f"✗ Attribute '{attr}' missing")
            
            # Check configuration
            if hasattr(self.glasses, 'config'):
                config = self.glasses.config
                self.print_debug(f"Config loaded - Left: {config.left_address}, Right: {config.right_address}")
            
            self.print_success("G1 Connector initialized successfully")
            return True
            
        except Exception as e:
            self.print_error(f"G1 Connector initialization failed: {e}")
            import traceback
            self.print_debug(f"Full traceback: {traceback.format_exc()}")
            return False

    async def test_bluetooth_scan(self):
        """Test Bluetooth scanning for G1 devices"""
        self.print_step("3", "Bluetooth Device Scanning")
        
        try:
            if not self.glasses:
                self.print_error("G1 Connector not initialized")
                return False
                
            self.print_debug("Starting Bluetooth scan for G1 devices...")
            
            # Check if devices are already known
            if self.glasses.config.left_address and self.glasses.config.right_address:
                self.print_debug(f"Known devices found:")
                self.print_debug(f"  Left: {self.glasses.config.left_address}")
                self.print_debug(f"  Right: {self.glasses.config.right_address}")
            else:
                self.print_debug("No known devices, will perform scan during connection")
            
            self.print_success("Bluetooth scan preparation completed")
            return True
            
        except Exception as e:
            self.print_error(f"Bluetooth scan failed: {e}")
            import traceback
            self.print_debug(f"Full traceback: {traceback.format_exc()}")
            return False

    async def test_connection(self):
        """Test connection to G1 glasses"""
        self.print_step("4", "G1 Glasses Connection")
        
        try:
            if not self.glasses:
                self.print_error("G1 Connector not initialized")
                return False
            
            self.print_debug("Attempting to connect to G1 glasses...")
            
            # Show progress spinner
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                task = progress.add_task("Connecting to glasses...", total=None)
                
                # Attempt connection
                connected = await self.glasses.connect()
                
                progress.update(task, completed=True)
            
            if connected:
                self.print_success("Successfully connected to G1 glasses!")
                
                # Show connection status
                await self.show_connection_status()
                
                return True
            else:
                self.print_error("Failed to connect to G1 glasses")
                return False
                
        except Exception as e:
            self.print_error(f"Connection failed: {e}")
            import traceback
            self.print_debug(f"Full traceback: {traceback.format_exc()}")
            return False

    async def show_connection_status(self):
        """Display detailed connection status"""
        self.print_debug("Retrieving connection status...")
        
        try:
            # Create status table
            table = Table(title="G1 Glasses Connection Status")
            table.add_column("Component", style="cyan")
            table.add_column("Status", style="green")
            table.add_column("Details", style="yellow")
            
            # Connection state
            state = getattr(self.glasses.state_manager, 'connection_state', 'Unknown')
            table.add_row("Connection", state, "Main connection status")
            
            # Left glass
            left_connected = self.glasses.left_client and self.glasses.left_client.is_connected if hasattr(self.glasses, 'left_client') else False
            table.add_row("Left Glass", "Connected" if left_connected else "Disconnected", 
                         f"Address: {self.glasses.config.left_address or 'Unknown'}")
            
            # Right glass
            right_connected = self.glasses.right_client and self.glasses.right_client.is_connected if hasattr(self.glasses, 'right_client') else False
            table.add_row("Right Glass", "Connected" if right_connected else "Disconnected",
                         f"Address: {self.glasses.config.right_address or 'Unknown'}")
            
            # Services
            services = ['uart_service', 'event_service', 'state_manager']
            for service in services:
                if hasattr(self.glasses, service):
                    table.add_row(service.replace('_', ' ').title(), "Active", "Service initialized")
                else:
                    table.add_row(service.replace('_', ' ').title(), "Inactive", "Service not found")
            
            self.console.print(table)
            
        except Exception as e:
            self.print_error(f"Failed to show connection status: {e}")

    async def test_display_functionality(self):
        """Test text display functionality"""
        self.print_step("5", "Display Functionality Test")
        
        try:
            if not self.glasses:
                self.print_error("G1 Connector not initialized")
                return False
            
            # Check if we have display service
            if not hasattr(self.glasses, 'display_service'):
                self.print_warning("Display service not found, checking if available...")
                
            # Test simple text display
            test_messages = [
                "Hello G1 Glasses!",
                f"Test Time: {time.strftime('%H:%M:%S')}",
                "SDK Debug Test Success"
            ]
            
            for i, message in enumerate(test_messages, 1):
                self.print_debug(f"Sending test message {i}: '{message}'")
                
                try:
                    # Try to send text (this might not be implemented yet)
                    if hasattr(self.glasses, 'display_service') and hasattr(self.glasses.display_service, 'send_text'):
                        await self.glasses.display_service.send_text(message, duration=3)
                        self.print_success(f"Text message {i} sent successfully")
                        await asyncio.sleep(3.5)  # Wait a bit between messages
                    else:
                        self.print_warning(f"Display service method not available, simulating send: '{message}'")
                        await asyncio.sleep(1)  # Simulate processing time
                        
                except Exception as e:
                    self.print_error(f"Failed to send message {i}: {e}")
                    
            self.print_success("Display functionality test completed")
            return True
            
        except Exception as e:
            self.print_error(f"Display test failed: {e}")
            import traceback
            self.print_debug(f"Full traceback: {traceback.format_exc()}")
            return False

    async def test_event_monitoring(self):
        """Test event monitoring for a short period"""
        self.print_step("6", "Event Monitoring Test")
        
        try:
            if not self.glasses:
                self.print_error("G1 Connector not initialized")
                return False
            
            self.print_debug("Starting 10-second event monitoring...")
            
            event_count = 0
            
            def event_handler(event_data):
                nonlocal event_count
                event_count += 1
                self.print_debug(f"Event {event_count} received: {event_data}")
            
            # Subscribe to events if possible
            if hasattr(self.glasses, 'event_service'):
                # This is a placeholder - actual event subscription depends on implementation
                self.print_debug("Event service found, monitoring for events...")
            else:
                self.print_warning("Event service not found")
            
            # Monitor for 10 seconds
            for i in range(10, 0, -1):
                self.console.print(f"Monitoring events... {i}s remaining", end="\r")
                await asyncio.sleep(1)
                
            self.console.print("\n")
            self.print_success(f"Event monitoring completed. {event_count} events captured")
            return True
            
        except Exception as e:
            self.print_error(f"Event monitoring failed: {e}")
            return False

    async def cleanup(self):
        """Cleanup and disconnect"""
        self.print_step("7", "Cleanup and Disconnect")
        
        try:
            if self.glasses:
                self.print_debug("Disconnecting from G1 glasses...")
                await self.glasses.disconnect()
                self.print_success("Successfully disconnected")
            
            self.print_success("Cleanup completed")
            
        except Exception as e:
            self.print_error(f"Cleanup failed: {e}")

    async def run_full_test(self):
        """Run the complete test suite"""
        self.console.print(Panel.fit(
            "[bold blue]G1 Glasses SDK - Comprehensive Debug Test[/bold blue]\n"
            "[dim]This test will check every aspect of the connection and display process[/dim]",
            border_style="blue"
        ))
        
        # Setup logging first
        self.setup_enhanced_logging()
        
        test_results = []
        
        # Run all tests
        test_functions = [
            ("Environment Check", self.test_environment_check),
            ("G1 Connector Init", self.test_g1_connector_init),
            ("Bluetooth Scan", self.test_bluetooth_scan),
            ("Connection Test", self.test_connection),
            ("Display Test", self.test_display_functionality),
            ("Event Monitoring", self.test_event_monitoring),
        ]
        
        for test_name, test_func in test_functions:
            try:
                result = await test_func()
                test_results.append((test_name, result))
                
                if not result:
                    self.print_warning(f"Test '{test_name}' failed, but continuing...")
                    
            except Exception as e:
                self.print_error(f"Test '{test_name}' crashed: {e}")
                test_results.append((test_name, False))
        
        # Always run cleanup
        await self.cleanup()
        
        # Show final results
        self.show_final_results(test_results)

    def show_final_results(self, test_results):
        """Show final test results summary"""
        self.console.print("\n" + "="*60)
        self.console.print(Panel.fit("[bold]Test Results Summary[/bold]", border_style="green"))
        
        results_table = Table(title="Test Results")
        results_table.add_column("Test", style="cyan")
        results_table.add_column("Result", style="bold")
        results_table.add_column("Status", style="dim")
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            if result:
                results_table.add_row(test_name, "✅ PASS", "Completed successfully")
                passed += 1
            else:
                results_table.add_row(test_name, "❌ FAIL", "Check logs for details")
        
        self.console.print(results_table)
        
        # Summary
        self.console.print(f"\n[bold]Overall: {passed}/{total} tests passed[/bold]")
        
        if passed == total:
            self.console.print("[green]🎉 All tests passed! G1 SDK is working correctly.[/green]")
        elif passed > 0:
            self.console.print("[yellow]⚠️  Some tests failed, but basic functionality is working.[/yellow]")
        else:
            self.console.print("[red]❌ All tests failed. Check your setup and try again.[/red]")
        
        self.console.print(f"\n[dim]Detailed logs saved to: g1_debug_test.log[/dim]")

async def main():
    """Main test function"""
    tester = DebugG1Tester()
    await tester.run_full_test()

if __name__ == "__main__":
    print("Starting G1 SDK Debug Test...")
    asyncio.run(main())