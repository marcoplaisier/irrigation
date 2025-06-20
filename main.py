import machine
import time
import json
import ubinascii
import sys
from umqtt.simple import MQTTClient
from wifi_connection import connect_wifi

class WaterMeterDetector:
    def __init__(self, config_file="config.json"):
        self.config = self._load_config(config_file)
        self.sensor_pin = machine.Pin(self.config["sensor"]["pin"], machine.Pin.IN, machine.Pin.PULL_UP)
        self.last_state = self.sensor_pin.value()
        self.last_trigger_time = 0
        self.debounce_time = self.config["sensor"]["debounce_ms"]
        self.cumulative_usage = self._load_cumulative_usage()
        self.mqtt_client = None
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
            print(f"Connecting to MQTT broker: {self.config['mqtt']['broker']}:{self.config['mqtt']['port']}")
            print(f"Using client ID: {client_id}")
            print(f"Using username: {self.config['mqtt']['user']}")
            
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
            print("MQTT connected successfully")
            
            # Subscribe to command topic for receiving new cumulative values
            command_topic = self.config["homeassistant"]["command_topic"]
            self.mqtt_client.set_callback(self._mqtt_callback)
            self.mqtt_client.subscribe(command_topic)
            
            # Send birth message and device discovery
            self._send_discovery_message()
            self._send_birth_message()
            
            # Send initial cumulative value
            self._send_water_usage()
            
            
        except OSError as e:
            print(f"MQTT connection failed - Network error: {e}")
            if e.args[0] == -2:
                print("Error -2: Check broker address, port, and network connectivity")
            self.mqtt_client = None
        except Exception as e:
            print(f"MQTT connection failed: {e}")
            self.mqtt_client = None
    
    def _send_birth_message(self):
        if self.mqtt_client:
            try:
                availability_topic = self.config["homeassistant"]["availability_topic"]
                self.mqtt_client.publish(availability_topic, "online")
                print("Birth message sent")
            except Exception as e:
                print(f"Birth message failed: {e}")
    
    def _send_discovery_message(self):
        if self.mqtt_client:
            try:
                ha_config = self.config["homeassistant"]
                discovery_message = {
                    "name": ha_config["device"]["name"],
                    "device_class": ha_config["device"]["device_class"],
                    "state_topic": ha_config["state_topic"],
                    "command_topic": ha_config["command_topic"],
                    "unit_of_measurement": ha_config["device"]["unit_of_measurement"],                    
                    "unique_id": ha_config["device"]["unique_id"],
                    "availability_topic": ha_config["availability_topic"],
                    "device": ha_config["device"]["device_info"]
                }
                
                discovery_topic = ha_config["discovery_topic"]
                self.mqtt_client.publish(discovery_topic, json.dumps(discovery_message))
                print("Home Assistant discovery message sent")
            except Exception as e:
                print(f"Discovery message failed: {e}")
    
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
            if topic.decode() == command_topic:
                new_value = float(msg.decode())
                self.cumulative_usage = new_value
                self._save_cumulative_usage()
                print(f"Cumulative usage set to: {self.cumulative_usage}L")
                self._send_water_usage()
        except (ValueError, UnicodeDecodeError) as e:
            print(f"Invalid command received: {e}")
    
    def _send_water_usage(self):
        if self.mqtt_client:
            try:
                state_topic = self.config["homeassistant"]["state_topic"]
                self.mqtt_client.publish(state_topic, str(self.cumulative_usage))
                print(f"Water usage sent: {self.cumulative_usage}L")
            except Exception as e:
                print(f"MQTT publish failed: {e}")
        else:
            print("MQTT not available, usage logged locally")
    
    def monitor(self):
        print("Water meter detector started")
        while True:
            current_state = self.sensor_pin.value()
            current_time = time.ticks_ms()
            
            if current_state != self.last_state:
                if current_state == 0 and time.ticks_diff(current_time, self.last_trigger_time) > self.debounce_time:
                    self.cumulative_usage += 1.0
                    self._save_cumulative_usage()
                    print(f"Water meter rotation detected - Total: {self.cumulative_usage}L")
                    self._send_water_usage()
                    self.last_trigger_time = current_time
                
                self.last_state = current_state
            
            # Check for MQTT messages
            if self.mqtt_client:
                try:
                    self.mqtt_client.check_msg()
                except Exception as e:
                    print(f"MQTT message check failed: {e}")
            
            time.sleep_ms(10)

if __name__ == "__main__":
    if connect_wifi():
        detector = WaterMeterDetector()
        detector.monitor()
    else:
        print("Cannot start without WiFi connection")
        sys.exit(1)
