import machine
import time
import json
import ubinascii
import sys
import gc
import network
from umqtt.simple import MQTTClient
from wifi_connection import connect_wifi, get_network_status

class Logger:
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3
    
    def __init__(self, level=INFO):
        self.level = level
        self.levels = ["DEBUG", "INFO", "WARN", "ERROR"]
    
    def _log(self, level, message):
        if level >= self.level:
            timestamp = time.time()
            level_name = self.levels[level]
            print(f"[{timestamp:.0f}] {level_name}: {message}")
    
    def debug(self, message):
        self._log(self.DEBUG, message)
    
    def info(self, message):
        self._log(self.INFO, message)
    
    def warn(self, message):
        self._log(self.WARN, message)
    
    def error(self, message):
        self._log(self.ERROR, message)

class WaterMeterDetector:
    def __init__(self, config_file="config.json"):
        self.logger = Logger(Logger.INFO)
        self.config = self._load_config(config_file)
        self.sensor_pin = machine.Pin(self.config["sensor"]["pin"], machine.Pin.IN, machine.Pin.PULL_UP)
        self.last_state = self.sensor_pin.value()
        self.last_trigger_time = 0
        self.debounce_time = self.config["sensor"]["debounce_ms"]
        self.min_pulse_width = self.config["sensor"].get("min_pulse_width_ms", 10)
        self.max_pulse_width = self.config["sensor"].get("max_pulse_width_ms", 2000)
        self.state_change_time = 0
        self.expecting_high = False
        self.cumulative_usage = self._load_cumulative_usage()
        self.mqtt_client = None
        self.start_time = time.time()
        self.last_heartbeat = 0
        self.heartbeat_interval = 300  # 5 minutes
        self.last_attributes_update = 0
        self.attributes_update_interval = 300  # 5 minutes
        self.mqtt_reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self._setup_mqtt()
        
    def _load_config(self, filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except OSError:
            print(f"ERROR: Configuration file '{filename}' not found!")
            print("Please create a config.json file with sensor and MQTT settings.")
            sys.exit(1)
        except ValueError as e:
            print(f"ERROR: Invalid JSON in configuration file: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Failed to load configuration: {e}")
            sys.exit(1)
    
    def _setup_mqtt(self):
        try:
            client_id = ubinascii.hexlify(machine.unique_id())
            self.logger.info(f"Connecting to MQTT broker: {self.config['mqtt']['broker']}:{self.config['mqtt']['port']}")
            self.logger.debug(f"Using client ID: {client_id}")
            self.logger.debug(f"Using username: {self.config['mqtt']['user']}")
            
            availability_topic = self.config["homeassistant"]["availability_topic"]
            
            self.mqtt_client = MQTTClient(
                client_id,
                self.config["mqtt"]["broker"],
                port=self.config["mqtt"]["port"],
                user=self.config["mqtt"]["user"],
                password=self.config["mqtt"]["password"]
            )
            
            # Set last will message before connecting
            self.mqtt_client.set_last_will(availability_topic, "offline")
            
            self.mqtt_client.connect()
            self.logger.info("MQTT connected successfully")
            
            # Subscribe to command topics
            command_topic = self.config["homeassistant"]["command_topic"]
            diagnostic_topic = self.config["homeassistant"].get("diagnostic_topic", "homeassistant/sensor/water_meter/diagnostic")
            self.mqtt_client.set_callback(self._mqtt_callback)
            self.mqtt_client.subscribe(command_topic)
            self.mqtt_client.subscribe(diagnostic_topic)
            
            # Send birth message and device discovery
            self._send_discovery_message()
            self._send_birth_message()
            
            # Send initial cumulative value
            self._send_water_usage()
            
            
        except OSError as e:
            self.logger.error(f"MQTT connection failed - Network error: {e}")
            if e.args[0] == -2:
                self.logger.error("Error -2: Check broker address, port, and network connectivity")
            self.mqtt_client = None
        except Exception as e:
            self.logger.error(f"MQTT connection failed: {e}")
            self.mqtt_client = None
    
    def _send_birth_message(self):
        if self.mqtt_client:
            try:
                availability_topic = self.config["homeassistant"]["availability_topic"]
                self.mqtt_client.publish(availability_topic, "online")
                self.logger.info("Birth message sent")
            except Exception as e:
                self.logger.error(f"Birth message failed: {e}")
    
    def _send_discovery_message(self):
        if self.mqtt_client:
            try:
                ha_config = self.config["homeassistant"]
                discovery_message = {
                    "name": ha_config["device"]["name"],
                    "device_class": ha_config["device"]["device_class"],
                    "state_topic": ha_config["state_topic"],
                    "json_attributes_topic": ha_config["json_attributes_topic"],
                    "command_topic": ha_config["command_topic"],
                    "unit_of_measurement": ha_config["device"]["unit_of_measurement"],
                    "state_class": ha_config["device"]["state_class"],
                    "unique_id": ha_config["device"]["unique_id"],
                    "availability_topic": ha_config["availability_topic"],
                    "device": ha_config["device"]["device_info"]
                }
                
                discovery_topic = ha_config["discovery_topic"]
                self.mqtt_client.publish(discovery_topic, json.dumps(discovery_message))
                self.logger.info("Home Assistant discovery message sent")
            except Exception as e:
                self.logger.error(f"Discovery message failed: {e}")
    
    def _format_iso_timestamp(self, timestamp):
        # Convert Unix timestamp to ISO 8601 format
        # MicroPython doesn't have full datetime support, so we'll use a simple format
        return f"{timestamp:.0f}"
    
    def _load_cumulative_usage(self):
        try:
            with open('water_usage.txt', 'r') as f:
                return float(f.read().strip())
        except (OSError, ValueError):
            return 0.0
    
    def _save_cumulative_usage(self):
        try:
            with open('water_usage.txt', 'w') as f:
                f.write(str(self.cumulative_usage))
        except OSError as e:
            print(f"Failed to save cumulative usage: {e}")
    
    def _mqtt_callback(self, topic, msg):
        try:
            command_topic = self.config["homeassistant"]["command_topic"]
            diagnostic_topic = self.config["homeassistant"].get("diagnostic_topic", "homeassistant/sensor/water_meter/diagnostic")
            
            topic_str = topic.decode()
            if topic_str == command_topic:
                new_value = float(msg.decode())
                self.cumulative_usage = new_value
                self._save_cumulative_usage()
                self.logger.info(f"Cumulative usage set to: {self.cumulative_usage}L")
                self._send_water_usage()
            elif topic_str == diagnostic_topic:
                command = msg.decode().lower()
                if command == "status":
                    # Trigger an immediate attributes update
                    self._send_water_usage()
                elif command == "heartbeat":
                    self._send_heartbeat()
        except (ValueError, UnicodeDecodeError) as e:
            self.logger.warn(f"Invalid command received: {e}")
    
    def _send_water_usage(self):
        if self._is_mqtt_connected():
            try:
                state_topic = self.config["homeassistant"]["state_topic"]
                json_attributes_topic = self.config["homeassistant"]["json_attributes_topic"]
                
                # Send state value
                self.mqtt_client.publish(state_topic, str(self.cumulative_usage))
                
                # Gather diagnostic data for attributes
                wifi_rssi = self._get_wifi_signal_strength()
                system_stats = self._get_system_stats()
                
                attributes_data = {
                    "timestamp": int(time.time()),
                    "device_id": ubinascii.hexlify(machine.unique_id()).decode(),
                    "uptime_seconds": system_stats.get("uptime", 0),
                    "wifi_connected": get_network_status(),
                    "wifi_ssid": self.config['wifi']['ssid'],
                    "wifi_rssi_dbm": wifi_rssi,
                    "mqtt_connected": True,
                    "mqtt_broker": self.config['mqtt']['broker'],
                    "mqtt_reconnect_attempts": self.mqtt_reconnect_attempts,
                    "memory_free_bytes": system_stats.get("memory_free", 0),
                    "memory_used_bytes": system_stats.get("memory_used", 0),
                    "memory_total_bytes": system_stats.get("memory_total", 0),
                    "memory_usage_percent": system_stats.get("memory_usage_percent", 0),
                    "sensor_pin": self.config["sensor"]["pin"],
                    "sensor_debounce_ms": self.config["sensor"]["debounce_ms"]
                }
                
                # Send attributes
                self.mqtt_client.publish(json_attributes_topic, json.dumps(attributes_data))
                
                self.logger.debug(f"Water usage and attributes sent: {self.cumulative_usage}L")
                self.mqtt_reconnect_attempts = 0  # Reset on successful publish
            except Exception as e:
                self.logger.error(f"MQTT publish failed: {e}")
                self._handle_mqtt_error()
        else:
            self.logger.warn("MQTT not available, usage logged locally")
            self._attempt_mqtt_reconnect()
    
    def _is_mqtt_connected(self):
        """Check if MQTT client is connected"""
        return self.mqtt_client is not None
    
    def _handle_mqtt_error(self):
        """Handle MQTT connection errors"""
        self.logger.warn("MQTT error detected, marking client as disconnected")
        self.mqtt_client = None
        self.mqtt_reconnect_attempts += 1
    
    def _attempt_mqtt_reconnect(self):
        """Attempt to reconnect to MQTT broker"""
        if self.mqtt_reconnect_attempts < self.max_reconnect_attempts:
            self.logger.info(f"Attempting MQTT reconnection ({self.mqtt_reconnect_attempts + 1}/{self.max_reconnect_attempts})")
            if get_network_status():
                self._setup_mqtt()
            else:
                self.logger.warn("WiFi not connected, cannot reconnect MQTT")
        else:
            self.logger.error("Max MQTT reconnection attempts reached")
    
    def _get_wifi_signal_strength(self):
        """Get WiFi signal strength in dBm"""
        try:
            wlan = network.WLAN(network.STA_IF)
            if wlan.isconnected():
                # scan() returns list of tuples: (ssid, bssid, channel, RSSI, authmode, hidden)
                scan_results = wlan.scan()
                current_ssid = self.config['wifi']['ssid']
                for result in scan_results:
                    if result[0].decode() == current_ssid:
                        return result[3]  # RSSI value
            return None
        except Exception as e:
            self.logger.debug(f"Failed to get WiFi signal strength: {e}")
            return None
    
    def _get_system_stats(self):
        """Get system statistics"""
        try:
            uptime = time.time() - self.start_time
            free_memory = gc.mem_free()
            allocated_memory = gc.mem_alloc()
            total_memory = free_memory + allocated_memory
            
            return {
                "uptime": int(uptime),
                "memory_free": free_memory,
                "memory_used": allocated_memory,
                "memory_total": total_memory,
                "memory_usage_percent": int((allocated_memory / total_memory) * 100)
            }
        except Exception as e:
            self.logger.debug(f"Failed to get system stats: {e}")
            return {}
    
    def _send_heartbeat(self):
        """Send heartbeat message as Home Assistant logbook event"""
        if not self._is_mqtt_connected():
            return
            
        try:
            wifi_rssi = self._get_wifi_signal_strength()
            system_stats = self._get_system_stats()
            
            # Format uptime in human readable format
            uptime_seconds = system_stats.get("uptime", 0)
            uptime_minutes = uptime_seconds // 60
            uptime_hours = uptime_minutes // 60
            uptime_days = uptime_hours // 24
            
            if uptime_days > 0:
                uptime_str = f"{uptime_days}d {uptime_hours % 24}h"
            elif uptime_hours > 0:
                uptime_str = f"{uptime_hours}h {uptime_minutes % 60}m"
            else:
                uptime_str = f"{uptime_minutes}m"
            
            # Create logbook event data
            logbook_event = {
                "name": "Water Meter",
                "message": f"Heartbeat - Uptime: {uptime_str}, WiFi: {wifi_rssi}dBm, Memory: {system_stats.get('memory_usage_percent', 0)}%, Usage: {self.cumulative_usage}L",
                "entity_id": "sensor.water_usage"
            }
            
            # Send to Home Assistant logbook service topic
            logbook_topic = "homeassistant/logbook"
            self.mqtt_client.publish(logbook_topic, json.dumps(logbook_event))
            self.logger.info(f"Heartbeat logbook event sent - Uptime: {uptime_str}, WiFi: {wifi_rssi}dBm, Memory: {system_stats.get('memory_usage_percent', 0)}%")
            
        except Exception as e:
            self.logger.error(f"Failed to send heartbeat: {e}")
            self._handle_mqtt_error()
    
    
    def _check_heartbeat(self):
        """Check if it's time to send a heartbeat"""
        current_time = time.time()
        if current_time - self.last_heartbeat >= self.heartbeat_interval:
            self._send_heartbeat()
            self.last_heartbeat = current_time
    
    def _check_attributes_update(self):
        """Check if it's time to send an attributes update"""
        current_time = time.time()
        if current_time - self.last_attributes_update >= self.attributes_update_interval:
            self._send_water_usage()
            self.last_attributes_update = current_time
    
    def _validate_state_change(self, new_state, current_time):
        """Validate that state change is not too rapid (basic debouncing)"""
        # Simple time-based debouncing for state changes
        if hasattr(self, 'last_state_change_time'):
            time_diff = time.ticks_diff(current_time, self.last_state_change_time)
            if time_diff < 5:  # 5ms minimum between state changes
                self.logger.debug(f"State change too rapid: {time_diff}ms")
                return False
        
        self.last_state_change_time = current_time
        return True
    
    def _validate_pulse_width(self, current_time):
        """Validate that pulse width is within acceptable range"""
        if not hasattr(self, 'state_change_time'):
            return False
            
        pulse_width = time.ticks_diff(current_time, self.state_change_time)
        
        if pulse_width < self.min_pulse_width:
            self.logger.debug(f"Pulse too short: {pulse_width}ms < {self.min_pulse_width}ms")
            return False
            
        if pulse_width > self.max_pulse_width:
            self.logger.debug(f"Pulse too long: {pulse_width}ms > {self.max_pulse_width}ms")
            return False
            
        self.logger.debug(f"Valid pulse width: {pulse_width}ms")
        return True
    
    def monitor(self):
        self.logger.info("Water meter detector started")
        while True:
            current_state = self.sensor_pin.value()
            current_time = time.ticks_ms()
            
            if current_state != self.last_state:
                if self._validate_state_change(current_state, current_time):
                    if current_state == 0:
                        # Falling edge - start of pulse
                        self.state_change_time = current_time
                        self.expecting_high = True
                        self.logger.debug("Pulse started")
                    else:
                        # Rising edge - end of pulse
                        if self.expecting_high and self._validate_pulse_width(current_time):
                            # Valid rotation detected
                            if time.ticks_diff(current_time, self.last_trigger_time) > self.debounce_time:
                                self.cumulative_usage += 1.0
                                self._save_cumulative_usage()
                                self.logger.info(f"Water meter rotation detected - Total: {self.cumulative_usage}L")
                                self._send_water_usage()
                                self.last_trigger_time = current_time
                                self.logger.debug("Valid rotation confirmed")
                        self.expecting_high = False
                
                self.last_state = current_state
            
            # Check for MQTT messages
            if self.mqtt_client:
                try:
                    self.mqtt_client.check_msg()
                except Exception as e:
                    self.logger.warn(f"MQTT message check failed: {e}")
                    self._handle_mqtt_error()
            
            # Check if we need to send a heartbeat
            self._check_heartbeat()
            
            # Check if we need to send an attributes update
            self._check_attributes_update()
            
            # Attempt reconnection if disconnected
            if not self._is_mqtt_connected():
                self._attempt_mqtt_reconnect()
            
            time.sleep_ms(10)

if __name__ == "__main__":
    if connect_wifi():
        detector = WaterMeterDetector()
        detector.monitor()
    else:
        print("Cannot start without WiFi connection")
        sys.exit(1)
