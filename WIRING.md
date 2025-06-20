# Water Meter Detector Wiring

## Hardware Components
- Raspberry Pi Pico (MicroPython)
- LJ18A3-8-Z/BX Inductive Proximity Sensor

## Wiring Connections

### LJ18A3-8-Z/BX Sensor
| Wire Color | Connection | Pico Pin |
|------------|------------|----------|
| Blue       | Ground     | GND      |
| Brown      | VCC        | 3V3      |
| Black      | Signal     | GP3      |

## Setup Instructions
1. Connect sensor wires according to the table above
2. Position sensor above rotating water meter disc
3. Adjust distance so metal portions are detected
4. Configure MQTT broker settings in `config.json`
5. Upload `main.py` and `config.json` to Pico
6. Run the program

## Configuration
Edit `config.json` to customize:
- Sensor pin (default: GP3)
- Debounce timing (default: 50ms)
- MQTT broker settings
- Home Assistant topic