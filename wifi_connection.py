import network
import time
import json

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def connect_wifi():
    config = load_config()
    wifi_config = config['wifi']
    
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    if not wlan.isconnected():
        print(f"Connecting to WiFi network: {wifi_config['ssid']}")
        wlan.connect(wifi_config['ssid'], wifi_config['password'])
        
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            print("Waiting for connection...")
            time.sleep(1)
            timeout -= 1
    
    if wlan.isconnected():
        print(f"WiFi connected! IP: {wlan.ifconfig()[0]}")
        return True
    else:
        print("Failed to connect to WiFi")
        return False

def get_network_status():
    wlan = network.WLAN(network.STA_IF)
    return wlan.isconnected()