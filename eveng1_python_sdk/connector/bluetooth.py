"""
Bluetooth specific functionality for G1 glasses
"""
import asyncio
import time
from bleak import BleakClient, BleakScanner
from typing import Optional
from rich.table import Table

from utils.constants import (
    UUIDS, COMMANDS, EventCategories, StateEvent, 
    StateColors, StateDisplay, ConnectionState
)
from utils.logger import user_guidance
from connector.pairing import PairingManager

class BLEManager:
    """Manages BLE connections for G1 glasses"""
    
    def __init__(self, connector):
        """Initialize BLE manager"""
        self.connector = connector
        self.logger = connector.logger
        self._error_count = 0
        self._last_error = None
        self._silent_mode = False
        self._last_heartbeat = None
        self._monitoring_task = None
        self.pairing_manager = PairingManager(connector)
        self._shutting_down = False

    async def scan_for_glasses(self) -> bool:
        """Scan for G1 glasses and save their addresses"""
        try:
            self.connector.state_manager.set_connection_state(ConnectionState.SCANNING)
            self.logger.info("Starting scan for glasses...")
            user_guidance(self.logger, "\n[yellow]Scanning for G1 glasses...[/yellow]")
            
            left_found = right_found = False
            
            # STEP 1: Check Windows connected devices first
            self.logger.info("[INFO] Checking Windows connected devices...")
            connected_g1_devices = await self._get_windows_connected_g1_devices()
            
            for device_info in connected_g1_devices:
                name = device_info['name']
                address = device_info['address']
                self.logger.info(f"[green]Found connected G1 device: {name} ({address})[/green]")
                
                # Try to identify left/right
                if "_L_" in name.upper() or "LEFT" in name.upper():
                    self.connector.config.left_address = address
                    self.connector.config.left_name = name
                    left_found = True
                    user_guidance(self.logger, f"[green]Found connected left glass: {name}[/green]")
                elif "_R_" in name.upper() or "RIGHT" in name.upper():
                    self.connector.config.right_address = address
                    self.connector.config.right_name = name
                    right_found = True
                    user_guidance(self.logger, f"[green]Found connected right glass: {name}[/green]")
            
            # STEP 2: If we don't have both, scan for available devices
            if not (left_found and right_found):
                self.logger.info("[INFO] Scanning for available BLE devices...")
                devices = await BleakScanner.discover(timeout=15.0)
                
                # Log all found devices for debugging
                self.logger.info(f"Found {len(devices)} available devices:")
                for device in devices:
                    device_name = device.name or "Unnamed"
                    self.logger.info(f"  {device_name} ({device.address})")
                
                # Look for G1 glasses with multiple patterns
                g1_devices = []
                for device in devices:
                    if device.name:
                        # Check for various G1 naming patterns
                        if any(pattern in device.name for pattern in ["_L_", "_R_", "G1", "Even", "LE-"]):
                            g1_devices.append(device)
                            self.logger.info(f"[green]Potential G1 device: {device.name} ({device.address})[/green]")
                            
                            # Try to identify left/right (only if not already found)
                            if not left_found and ("_L_" in device.name or "Left" in device.name):
                                self.connector.config.left_address = device.address
                                self.connector.config.left_name = device.name
                                left_found = True
                                user_guidance(self.logger, f"[green]Found available left glass: {device.name}[/green]")
                            elif not right_found and ("_R_" in device.name or "Right" in device.name):
                                self.connector.config.right_address = device.address
                                self.connector.config.right_name = device.name
                                right_found = True
                                user_guidance(self.logger, f"[green]Found available right glass: {device.name}[/green]")
                
                # If we found G1 devices but couldn't identify left/right, assign them arbitrarily
                if len(g1_devices) >= 1 and not (left_found and right_found):
                    self.logger.info("[yellow]Found G1 devices, assigning missing sides...[/yellow]")
                    available_devices = [d for d in g1_devices if d.address not in [self.connector.config.left_address, self.connector.config.right_address]]
                    
                    if not left_found and available_devices:
                        self.connector.config.left_address = available_devices[0].address
                        self.connector.config.left_name = available_devices[0].name
                        left_found = True
                        user_guidance(self.logger, f"[green]Assigned as left glass: {available_devices[0].name}[/green]")
                        available_devices.pop(0)
                    
                    if not right_found and available_devices:
                        self.connector.config.right_address = available_devices[0].address
                        self.connector.config.right_name = available_devices[0].name
                        right_found = True
                        user_guidance(self.logger, f"[green]Assigned as right glass: {available_devices[0].name}[/green]")

            if not (left_found and right_found):
                self.connector.state_manager.set_connection_state(ConnectionState.DISCONNECTED)
                user_guidance(self.logger, "\n[yellow]Glasses not found. Please ensure:[/yellow]")
                user_guidance(self.logger, "1. Glasses are properly prepared and seated in the powered cradle:")
                user_guidance(self.logger, "   - First close the left temple/arm")
                user_guidance(self.logger, "   - Then close the right temple/arm")
                user_guidance(self.logger, "   - Place glasses in cradle with both arms closed")
                user_guidance(self.logger, "2. Bluetooth is enabled on your computer (sometimes wifi on your computer can interfere with bluetooth)")
                user_guidance(self.logger, "3. Bluetooth is disabled on other nearby devices that have paired with the glasses")
                user_guidance(self.logger, "4. Glasses have not been added to Windows Bluetooth manager (remove if present)")
                user_guidance(self.logger, "5. If still not working, connect with the offical app and restart the glasses, then try again.")
                return False

            self.connector.config.save()
            return True

        except Exception as e:
            self.logger.error(f"Scan failed: {e}")
            self.connector.state_manager.set_connection_state(ConnectionState.DISCONNECTED)
            user_guidance(self.logger, f"\n[red]Error during scan: {e}[/red]")
            return False

    async def connect_to_glasses(self) -> bool:
        """Connect to glasses with robust retry logic"""
        try:
            self.logger.info("[yellow]Connecting to G1, please wait...[/yellow]")
            
            self.connector.state_manager.set_connection_state(ConnectionState.CONNECTING)
            
            # Skip pre-disconnect - we'll work with Windows connections directly
            
            # Strategy 0: Try to restore addresses from saved names if missing
            if not self.connector.config.left_address and hasattr(self.connector.config, 'left_name'):
                if "CCF7207288DB" in str(self.connector.config.left_name):
                    self.connector.config.left_address = "CC:F7:20:72:88:DB"
                    self.logger.info("Restored left address from saved name")
            
            if not self.connector.config.right_address and hasattr(self.connector.config, 'right_name'):
                if "DAD8C8AF5258" in str(self.connector.config.right_name):
                    self.connector.config.right_address = "DA:D8:C8:AF:52:58"
                    self.logger.info("Restored right address from saved name")
            
            # Strategy 1: Try with saved addresses if they exist
            left_connected = False
            right_connected = False
            
            if self.connector.config.left_address and self.connector.config.right_address:
                self.logger.info("Attempting connection with saved addresses...")
                self.logger.info(f"Left: {self.connector.config.left_address}")
                self.logger.info(f"Right: {self.connector.config.right_address}")
                left_connected = await self._connect_glass('left')
                right_connected = await self._connect_glass('right')
            
            # Strategy 2: If both failed or no saved addresses, try scanning and pairing
            if not left_connected and not right_connected:
                self.logger.info("Saved addresses failed or not found, attempting fresh pairing...")
                if await self.pairing_manager.verify_pairing():
                    left_connected = await self._connect_glass('left')
                    right_connected = await self._connect_glass('right')
            
            # Strategy 3: If still no success, clear saved addresses and try fresh scan
            if not left_connected and not right_connected:
                self.logger.info("Clearing saved addresses and attempting fresh scan...")
                # Clear potentially stale addresses
                old_left = self.connector.config.left_address
                old_right = self.connector.config.right_address
                
                self.connector.config.left_address = None
                self.connector.config.right_address = None
                self.connector.config.save()
                
                if await self.scan_for_glasses():
                    left_connected = await self._connect_glass('left')
                    right_connected = await self._connect_glass('right')
                else:
                    # If scan failed, restore old addresses
                    self.connector.config.left_address = old_left
                    self.connector.config.right_address = old_right
            
            # Strategy 4: If one glass connected but other failed, try fresh scan for the missing one
            if (left_connected and not right_connected) or (right_connected and not left_connected):
                self.logger.info("One glass connected, attempting fresh scan for missing glass...")
                # Clear and rescan for both
                self.connector.config.left_address = None
                self.connector.config.right_address = None
                self.connector.config.save()
                
                # Disconnect the working one temporarily to rescan
                if left_connected and self.connector.left_client:
                    await self.connector.left_client.disconnect()
                    self.connector.left_client = None
                if right_connected and self.connector.right_client:
                    await self.connector.right_client.disconnect()
                    self.connector.right_client = None
                
                if await self.scan_for_glasses():
                    left_connected = await self._connect_glass('left')
                    right_connected = await self._connect_glass('right')
            
            # Evaluate success - we need BOTH glasses connected
            if left_connected and right_connected:
                # Start command manager and heartbeat
                await self.connector.command_manager.start()
                self.logger.info("[green]BOTH GLASSES CONNECTED SUCCESSFULLY[/green]")
                self.connector.state_manager.set_connection_state(ConnectionState.CONNECTED)
                # Start monitoring
                self._monitoring_task = asyncio.create_task(self._monitor_connection_quality())
                return True
            else:
                # Disconnect any partial connections
                if left_connected and self.connector.left_client:
                    try:
                        await self.connector.left_client.disconnect()
                        self.connector.left_client = None
                    except:
                        pass
                if right_connected and self.connector.right_client:
                    try:
                        await self.connector.right_client.disconnect()
                        self.connector.right_client = None
                    except:
                        pass
                
                # Log specific failure
                if left_connected and not right_connected:
                    self.logger.error("[red]LEFT glass connected but RIGHT glass failed[/red]")
                elif right_connected and not left_connected:
                    self.logger.error("[red]RIGHT glass connected but LEFT glass failed[/red]")
                else:
                    self.logger.error("[red]BOTH glasses failed to connect[/red]")
                
                self.logger.info("Troubleshooting tips:")
                self.logger.info("   - Make sure BOTH glasses are powered on")
                self.logger.info("   - Check Bluetooth is enabled") 
                self.logger.info("   - Try moving closer to glasses")
                self.logger.info("   - Try removing and re-pairing glasses in Windows Bluetooth settings")
                self.logger.info("   - Make sure both glasses are charged")
                self.connector.state_manager.set_connection_state(ConnectionState.DISCONNECTED)
                return False
                
        except Exception as e:
            self.logger.error(f"[red]Connection failed: {e}[/red]")
            self.connector.state_manager.set_connection_state(ConnectionState.DISCONNECTED)
            return False

    async def disconnect(self):
        """Disconnect from glasses"""
        try:
            self._shutting_down = True
            
            # Cancel monitoring task
            if self._monitoring_task:
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
                self._monitoring_task = None
                
            # Stop command manager
            await self.connector.command_manager.stop()
            
            # Disconnect both glasses
            for side in ['left', 'right']:
                client = getattr(self.connector, f"{side}_client", None)
                if client and client.is_connected:
                    await client.disconnect()
                    setattr(self.connector, f"{side}_client", None)
                    
            self.connector.state_manager.set_connection_state(ConnectionState.DISCONNECTED)
            
        except Exception as e:
            self.logger.error(f"Error during disconnect: {e}")

    def _create_status_table(self) -> Table:
        """Create status table with all required information"""
        table = Table(box=True, border_style="blue", title="G1 Glasses Status")
        
        # Connection states with colors
        for side in ['Left', 'Right']:
            client = getattr(self.connector, f"{side.lower()}_client", None)
            status = "[green]Connected[/green]" if client and client.is_connected else "[red]Disconnected[/red]"
            table.add_row(f"{side} Glass", status)
            
        # Physical state with appropriate color
        system_name, _ = StateEvent.get_physical_state(self.connector.state_manager._physical_state)
        state_colors = {
            "WEARING": "green",
            "TRANSITIONING": "yellow",
            "CRADLE": "blue",
            "CRADLE_CHARGING": "yellow",
            "CRADLE_FULL": "bright_blue",
            "UNKNOWN": "red"
        }
        color = state_colors.get(system_name, "white")
        state = self.connector.state_manager.physical_state
        table.add_row("State", f"[{color}]{state}[/{color}]")
        
        # Add last interaction if any
        interaction = self.connector.state_manager.last_interaction
        if interaction and interaction != "None":
            table.add_row("Last Interaction", f"[{StateColors.HIGHLIGHT}]{interaction}[/{StateColors.HIGHLIGHT}]")
        
        # Last heartbeat timing
        if self._last_heartbeat:
            elapsed = time.time() - self._last_heartbeat
            table.add_row("Last Heartbeat", f"{elapsed:.1f}s ago")
        
        # Silent mode status
        table.add_row("Silent Mode", 
                     f"[{StateColors.WARNING}]On[/{StateColors.WARNING}]" if self._silent_mode 
                     else f"[{StateColors.NEUTRAL}]Off[/{StateColors.NEUTRAL}]")
        
        # Error information
        if self._error_count > 0:
            table.add_row("Errors", f"[{StateColors.ERROR}]{self._error_count}[/{StateColors.ERROR}]")
            if self._last_error:
                table.add_row("Last Error", f"[{StateColors.ERROR}]{self._last_error}[/{StateColors.ERROR}]")
        
        return table

    async def _verify_connection(self, client: BleakClient, glass_name: str) -> bool:
        """Verify connection and services are available"""
        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self.logger.debug(f"Verifying {glass_name} connection...")
                    
                    # Get UART service
                    uart_service = client.services.get_service(UUIDS.UART_SERVICE)
                    if not uart_service:
                        if attempt < max_retries - 1:
                            self.logger.debug(f"UART service not found for {glass_name}, retrying...")
                            continue
                        self.logger.error(f"UART service not found for {glass_name}")
                        return False
                    
                    # Verify characteristics
                    uart_tx = uart_service.get_characteristic(UUIDS.UART_TX)
                    uart_rx = uart_service.get_characteristic(UUIDS.UART_RX)
                    
                    if not uart_tx or not uart_rx:
                        if attempt < max_retries - 1:
                            self.logger.debug(f"UART characteristics not found for {glass_name}, retrying...")
                            continue
                        self.logger.error(f"UART characteristics not found for {glass_name}")
                        return False
                    
                    self.logger.info(f"{glass_name} connection verified successfully")
                    return True
                    
                except Exception as e:
                    if attempt < max_retries - 1:
                        self.logger.debug(f"Error verifying {glass_name} connection (attempt {attempt + 1}): {e}")
                        await asyncio.sleep(1)
                        continue
                    self.logger.error(f"Error verifying {glass_name} connection: {e}")
                    return False
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in verification process for {glass_name}: {e}")
            return False

    async def send_heartbeat(self, client: BleakClient) -> None:
        """Send heartbeat command to specified glass"""
        await self.connector.command_manager.send_heartbeat(client)

    async def reconnect(self) -> bool:
        """Reconnect to both glasses"""
        try:
            await self.disconnect()
            return await self.connect_to_glasses()
        except Exception as e:
            self.logger.error(f"Reconnection failed: {e}")
            return False

    async def _monitor_connection_quality(self):
        """Monitor basic connection status"""
        self.logger.debug("Starting connection monitoring")
        
        while not self._shutting_down:
            try:
                # Check if clients are still connected
                for side in ['left', 'right']:
                    if self._shutting_down:
                        return
                        
                    client = getattr(self.connector, f"{side}_client", None)
                    if client and not client.is_connected:
                        self.logger.warning(f"{side.title()} glass disconnected")
                        self._error_count += 1
                        self._last_error = f"{side.title()} glass disconnected"
                
                await asyncio.sleep(10)
                    
            except Exception as e:
                if not self._shutting_down:
                    self._error_count += 1
                    self._last_error = str(e)
                    self.logger.error(f"Error in connection monitoring: {e}")
                await asyncio.sleep(10)

    async def verify_connection(self, client: BleakClient) -> bool:
        """Verify connection is working with heartbeat"""
        try:
            # Send initial heartbeat
            await self.send_heartbeat(client)
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < 2.0:  # 2 second timeout
                if self.connector.uart_service.last_heartbeat and \
                   self.connector.uart_service.last_heartbeat > start_time:
                    return True
                await asyncio.sleep(0.1)
            
            self.logger.warning("Connection verification failed - no heartbeat response")
            return False
            
        except Exception as e:
            self.logger.error(f"Error verifying connection: {e}")
            return False 

    def _update_connection_quality(self, side: str, rssi: Optional[int] = None, error: bool = False):
        """Update connection quality metrics"""
        if side not in self.connector._connection_quality:
            self.connector._connection_quality[side] = {'rssi': None, 'errors': 0}
            
        if rssi is not None:
            self.connector._connection_quality[side]['rssi'] = rssi
            
        if error:
            self.connector._connection_quality[side]['errors'] += 1 

    async def start_monitoring(self):
        """Start connection quality monitoring"""
        if not self._monitoring_task:
            self.logger.info("Starting connection quality monitoring")
            self._monitoring_task = asyncio.create_task(self._monitor_connection_quality())

    async def stop_monitoring(self):
        """Stop connection quality monitoring"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None 

    async def _heartbeat_loop(self):
        """Maintain connection with regular heartbeats"""
        seq = 0
        while True:
            try:
                if self.connector.left_client and self.connector.right_client:
                    seq = (seq + 1) & 0xFF
                    data = bytes([0x25, 0x06, 0x00, seq, 0x04, seq])
                    
                    # Send to both glasses in sequence
                    await self.send_command(self.connector.left_client, data)
                    self.logger.debug(f"Heartbeat sent to Left: {data.hex()}")
                    await asyncio.sleep(0.2)
                    
                    await self.send_command(self.connector.right_client, data)
                    self.logger.debug(f"Heartbeat sent to Right: {data.hex()}")
                    
                    self._last_heartbeat = time.time()
                    await asyncio.sleep(self.connector.config.heartbeat_interval)
                    
            except Exception as e:
                self._error_count += 1
                self._last_error = f"Heartbeat failed: {e}"
                self.logger.error(self._last_error)
                await asyncio.sleep(2)

    async def _handle_disconnect(self, side: str):
        """Handle disconnection and attempt reconnection"""
        if self._shutting_down:
            return False
            
        self.logger.warning(f"{side.title()} glass disconnected")
        self._error_count += 1
        self._last_error = f"{side.title()} glass disconnected"

        for attempt in range(self.connector.config.reconnect_attempts):
            if self._shutting_down:
                return False
                
            try:
                self.logger.info(f"Attempting to reconnect {side} glass (attempt {attempt + 1})")
                if await self._connect_glass(side):
                    self.logger.info(f"Successfully reconnected {side} glass")
                    return True
                await asyncio.sleep(self.connector.config.reconnect_delay)
            except Exception as e:
                self.logger.error(f"Reconnection attempt {attempt + 1} failed: {e}")
        
        return False

    async def _connect_glass(self, side: str) -> bool:
        """Connect to a single glass with disconnect callback"""
        try:
            address = getattr(self.connector.config, f"{side}_address")
            if not address:
                self.logger.warning(f"No {side} glass address configured - skipping")
                return False

            for attempt in range(self.connector.config.reconnect_attempts):
                try:
                    self.logger.info(f"Attempting to connect {side} glass (attempt {attempt + 1})")
                    
                    # First check if we can find an already connected client for this device
                    existing_client = None
                    
                    # SOLUTION: For Windows-connected devices, connect directly using address string
                    # This is the most reliable method when devices are already paired to Windows
                    self.logger.info(f"[INFO] Attempting direct connection to {side.title()} glass using address...")
                    
                    # Direct connection using just the MAC address - let Windows handle the rest
                    client = BleakClient(
                        address,  # Use address string directly
                        disconnected_callback=lambda c: asyncio.create_task(self._handle_disconnect(side))
                    )
                    
                    try:
                        await client.connect(timeout=self.connector.config.connection_timeout)
                    except Exception as conn_error:
                        error_str = str(conn_error).lower()
                        if "not found" in error_str:
                            self.logger.info(f"[INFO] {side.title()} glass still not found - trying address-only fallback...")
                            
                            # Final fallback: try with just the address
                            try:
                                client = BleakClient(address)
                                await client.connect(timeout=15.0)  # Longer timeout for problematic connections
                            except Exception as alt_error:
                                self.logger.warning(f"[WARNING] All connection methods failed: {alt_error}")
                                raise conn_error
                        else:
                            raise conn_error
                    
                    if client.is_connected:
                        # Verify the connection works
                        if await self._verify_connection(client, f"{side} glass"):
                            setattr(self.connector, f"{side}_client", client)
                            await self.connector.uart_service.start_notifications(client, side)
                            self.logger.info(f"[SUCCESS] {side.title()} glass connected successfully")
                            return True
                        else:
                            self.logger.warning(f"[FAILED] {side.title()} glass connected but verification failed")
                            await client.disconnect()
                    else:
                        self.logger.warning(f"[FAILED] {side.title()} glass connection failed")
                        
                    if attempt < self.connector.config.reconnect_attempts - 1:
                        await asyncio.sleep(self.connector.config.reconnect_delay)
                    
                except Exception as e:
                    error_msg = str(e)
                    if "not found" in error_msg.lower():
                        self.logger.warning(f"[NOT FOUND] {side.title()} glass not found (address: {address})")
                        self.logger.info(f"[HINT] Device might be connected to Windows. Try the 'Clear Saved Addresses' button.")
                    elif "timeout" in error_msg.lower():
                        self.logger.warning(f"[TIMEOUT] {side.title()} glass connection timeout")
                    elif "already connected" in error_msg.lower() or "in use" in error_msg.lower():
                        self.logger.warning(f"[BUSY] {side.title()} glass already in use by another process")
                        self.logger.info(f"[HINT] Try disconnecting from Windows Bluetooth settings or use 'Clear Saved Addresses'")
                    else:
                        self.logger.warning(f"[ERROR] {side.title()} glass connection error: {e}")
                    
                    if attempt < self.connector.config.reconnect_attempts - 1:
                        self.logger.debug(f"Retrying {side} glass connection in {self.connector.config.reconnect_delay}s...")
                        await asyncio.sleep(self.connector.config.reconnect_delay)
                        
            self.logger.warning(f"[FAILED] Failed to connect {side} glass after {self.connector.config.reconnect_attempts} attempts")
            return False
            
        except Exception as e:
            self.logger.error(f"Error connecting to {side} glass: {e}")
            return False 

    async def _force_disconnect_stuck_devices(self):
        """Force disconnect any G1 devices that might be stuck connected to Windows"""
        try:
            import subprocess
            self.logger.info("[INFO] Checking for stuck G1 device connections...")
            
            # Get list of connected G1 devices
            result = subprocess.run(
                'powershell -Command "Get-PnpDevice | Where-Object {($_.Name -like \'*G1*\' -or $_.Name -like \'*Even*\') -and $_.Status -eq \'OK\'} | Select-Object Name, InstanceId"',
                shell=True, capture_output=True, text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                self.logger.info("[INFO] Found connected G1 devices, attempting to disconnect...")
                # Disconnect them
                disconnect_result = subprocess.run(
                    'powershell -Command "Get-PnpDevice | Where-Object {($_.Name -like \'*G1*\' -or $_.Name -like \'*Even*\') -and $_.Status -eq \'OK\'} | Disable-PnpDevice -Confirm:$false"',
                    shell=True, capture_output=True, text=True
                )
                
                if disconnect_result.returncode == 0:
                    self.logger.info("[SUCCESS] Disconnected stuck G1 devices from Windows")
                    await asyncio.sleep(2)  # Wait for clean disconnection
                else:
                    self.logger.warning("[WARNING] Could not disconnect some G1 devices")
            else:
                self.logger.debug("[DEBUG] No stuck G1 devices found")
                
        except Exception as e:
            self.logger.warning(f"[WARNING] Error checking for stuck devices: {e}")

    async def _get_windows_connected_g1_devices(self):
        """Get G1 devices that are currently connected to Windows"""
        devices = []
        try:
            import subprocess
            import re
            
            # Get connected BLE devices from Windows
            result = subprocess.run(
                'powershell -Command "Get-PnpDevice | Where-Object {($_.Name -like \'*G1*\' -or $_.Name -like \'*Even*\') -and $_.Status -eq \'OK\'} | Select-Object Name, HardwareID"',
                shell=True, capture_output=True, text=True
            )
            
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                current_device = {}
                
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('Name') or line.startswith('----'):
                        continue
                    
                    # Try to parse device info
                    if 'G1' in line or 'Even' in line:
                        # Extract device name (everything before potential MAC address)
                        name = line.strip()
                        
                        # Extract MAC address from the name or use config
                        address = None
                        
                        # First try to extract from the device ID/name
                        if "CCF7207288DB" in line:
                            address = "CC:F7:20:72:88:DB"
                        elif "DAD8C8AF5258" in line:
                            address = "DA:D8:C8:AF:52:58"
                        elif "_L_" in name.upper():
                            address = self.connector.config.left_address if hasattr(self.connector.config, 'left_address') else None
                        elif "_R_" in name.upper():
                            address = self.connector.config.right_address if hasattr(self.connector.config, 'right_address') else None
                        
                        if address:
                            devices.append({
                                'name': name,
                                'address': address
                            })
                            self.logger.debug(f"Found Windows connected device: {name} -> {address}")
            
            # Alternative method: Check using bluetooth registry/WMI
            if not devices:
                try:
                    # Try using WMI to get bluetooth devices
                    wmi_result = subprocess.run(
                        'powershell -Command "Get-CimInstance -Namespace root/cimv2 -ClassName Win32_PnPEntity | Where-Object {$_.Name -like \'*G1*\' -or $_.Name -like \'*Even*\'} | Select-Object Name, DeviceID"',
                        shell=True, capture_output=True, text=True
                    )
                    
                    if wmi_result.returncode == 0 and wmi_result.stdout.strip():
                        # Parse WMI output for device info
                        lines = wmi_result.stdout.strip().split('\n')
                        for line in lines:
                            if 'G1' in line or 'Even' in line:
                                name = line.strip()
                                # Use saved addresses if names match
                                if "_L_" in name.upper() and hasattr(self.connector.config, 'left_address'):
                                    devices.append({
                                        'name': name,
                                        'address': self.connector.config.left_address
                                    })
                                elif "_R_" in name.upper() and hasattr(self.connector.config, 'right_address'):
                                    devices.append({
                                        'name': name,
                                        'address': self.connector.config.right_address
                                    })
                except Exception as e:
                    self.logger.debug(f"WMI query failed: {e}")
            
        except Exception as e:
            self.logger.warning(f"[WARNING] Error checking Windows connected devices: {e}")
        
        return devices

    def set_silent_mode(self, enabled: bool):
        """Toggle silent mode"""
        self._silent_mode = enabled
        # Log the change
        self.logger.info(f"Silent mode {'enabled' if enabled else 'disabled'}")
        # Update the status immediately
        self.connector.state_manager.update_status(self.get_status_data())

    def get_status_data(self) -> dict:
        """Get current status data for external display"""
        return {
            'connection': {
                'left': {
                    'connected': bool(self.connector.left_client and self.connector.left_client.is_connected),
                    'errors': self._error_count,
                    'last_error': self._last_error
                },
                'right': {
                    'connected': bool(self.connector.right_client and self.connector.right_client.is_connected),
                    'errors': self._error_count,
                    'last_error': self._last_error
                }
            },
            'heartbeat': self._last_heartbeat,
            'silent_mode': self._silent_mode
        } 