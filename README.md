# Irrigation Water Meter Detector

MicroPython-based water meter monitoring system using an LJ18A3-8-Z/BX inductive sensor with Home Assistant integration.

## Hardware Setup

See [WIRING.md](WIRING.md) for complete hardware wiring instructions.

## Configuration

1. Create a `config.json` file on your Raspberry Pi Pico:

```json
{
    "wifi": {
        "ssid": "your_wifi_network_name",
        "password": "your_wifi_password"
    },
    "sensor": {
        "pin": 3,
        "debounce_ms": 50
    },
    "mqtt": {
        "broker": "192.168.1.100",
        "port": 1883,
        "client_id": "pico_water_meter",
        "user": "your_mqtt_username",
        "password": "your_mqtt_password",
        "keep_alive_seconds": 30
    },
    "homeassistant": {
        "discovery_topic": "homeassistant/sensor/water_meter/config",
        "state_topic": "homeassistant/sensor/water_meter/state",
        "json_attributes_topic": "homeassistant/sensor/water_meter/attributes",
        "command_topic": "homeassistant/sensor/water_meter/set",
        "availability_topic": "homeassistant/sensor/water_meter/availability",
        "heartbeat_topic": "homeassistant/sensor/water_meter/heartbeat",
        "diagnostic_topic": "homeassistant/sensor/water_meter/diagnostic",
        "diagnostic_response_topic": "homeassistant/sensor/water_meter/diagnostic_response",
        "device": {
            "unique_id": "water_meter_001",
            "name": "Water Usage",
            "device_class": "water",
            "unit_of_measurement": "L",
            "device_info": {
                "identifiers": ["water_meter_001"],
                "name": "Water Meter",
                "model": "Generic Water Counter",
                "manufacturer": "DIY"
            }
        }
    }
}
```

2. Upload both `main.py` and `config.json` to your Pico
3. Configure Home Assistant (see below)

## Home Assistant Configuration

### 1. Enable MQTT Integration

If not already enabled, add MQTT to your Home Assistant:

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for and add **MQTT**
3. Configure your MQTT broker settings

### 2. Add MQTT Sensor

Add this to your `configuration.yaml`:

```yaml
mqtt:
  sensor:
    - name: "Water Meter Rotations"
      state_topic: "irrigation/water_meter"
      value_template: "{{ value_json.event }}"
      json_attributes_topic: "irrigation/water_meter"
      json_attributes_template: "{{ value_json | tojson }}"
      icon: mdi:water-pump
      
    - name: "Water Meter Last Rotation"
      state_topic: "irrigation/water_meter"
      value_template: "{{ value_json.timestamp | timestamp_local }}"
      device_class: timestamp
      icon: mdi:clock-outline
```

### 3. Create Automation (Optional)

Example automation to log water usage:

```yaml
automation:
  - alias: "Water Meter Rotation Detected"
    trigger:
      platform: mqtt
      topic: "irrigation/water_meter"
    condition:
      condition: template
      value_template: "{{ trigger.payload_json.event == 'rotation_detected' }}"
    action:
      - service: logbook.log
        data:
          name: "Water Meter"
          message: "Water meter rotation detected at {{ now().strftime('%H:%M:%S') }}"
      - service: counter.increment
        entity_id: counter.water_meter_rotations
```

### 4. Add Counter (Optional)

To track total rotations, add this to `configuration.yaml`:

```yaml
counter:
  water_meter_rotations:
    name: "Water Meter Total Rotations"
    icon: mdi:counter
    step: 1
```

### 5. Restart Home Assistant

After making configuration changes, restart Home Assistant to apply them.

## Usage

1. Position the sensor above your water meter's rotating disc
2. Ensure the sensor detects the metal portions of the disc
3. Power on the Pico - it will automatically start monitoring
4. Check Home Assistant for incoming sensor data

## Troubleshooting

- Check MQTT broker connectivity
- Verify sensor positioning and wiring
- Monitor Pico console output for error messages
- Ensure Home Assistant MQTT integration is working