import machine
import time
import json
import ubinascii
from umqtt.simple import MQTTClient

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
        except Exception as e:
            print(f"Error loading config: {e}")
            return self._default_config()
    
    def _default_config(self):
        return {
            "sensor": {
                "pin": 3,
                "debounce_ms": 50
            },
            "mqtt": {
                "broker": "homeassistant.local",
                "port": 1883,
                "topic": "irrigation/water_meter",
                "client_id": "pico_water_meter"
            }
        }
    
    def _setup_mqtt(self):
        try:
            client_id = ubinascii.hexlify(machine.unique_id())
            self.mqtt_client = MQTTClient(
                client_id,
                self.config["mqtt"]["broker"],
                port=self.config["mqtt"]["port"]
            )
            self.mqtt_client.connect()
            print("MQTT connected")
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
    detector = WaterMeterDetector()
    detector.monitor()