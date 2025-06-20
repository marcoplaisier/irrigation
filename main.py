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
            
            self.mqtt_client = MQTTClient(
                client_id,
                self.config["mqtt"]["broker"],
                port=self.config["mqtt"]["port"],
                user=self.config["mqtt"]["user"],
                password=self.config["mqtt"]["password"],
            )
            self.mqtt_client.connect()
            print("MQTT connected successfully")
        except OSError as e:
            print(f"MQTT connection failed - Network error: {e}")
            if e.args[0] == -2:
                print("Error -2: Check broker address, port, and network connectivity")
            self.mqtt_client = None
        except Exception as e:
            print(f"MQTT connection failed: {e}")
            self.mqtt_client = None
    
    def _send_detection(self):
        if self.mqtt_client:
            try:
                message = json.dumps({
                    "timestamp": time.time(),
                    "event": "rotation_detected",
                    "sensor": "LJ18A3-8-Z/BX"
                })
                self.mqtt_client.publish(self.config["mqtt"]["topic"], message)
                print("Detection sent to Home Assistant")
            except Exception as e:
                print(f"MQTT publish failed: {e}")
        else:
            print("MQTT not available, detection logged locally")
    
    def monitor(self):
        print("Water meter detector started")
        while True:
            current_state = self.sensor_pin.value()
            current_time = time.ticks_ms()
            
            if current_state != self.last_state:
                if current_state == 0 and time.ticks_diff(current_time, self.last_trigger_time) > self.debounce_time:
                    print("Metal detected - falling edge")
                    self._send_detection()
                    self.last_trigger_time = current_time
                
                self.last_state = current_state
            
            time.sleep_ms(10)

if __name__ == "__main__":
    if connect_wifi():
        detector = WaterMeterDetector()
        detector.monitor()
    else:
        print("Cannot start without WiFi connection")
        sys.exit(1)
