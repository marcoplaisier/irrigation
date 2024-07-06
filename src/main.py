import json

import uasyncio as asyncio

from src.config import local_config
from src.mqtt.mqtt_as import MQTTClient
from src.service.valvecontroller import ValveController


class IrrigationMQTTClient:
    def __init__(self):
        MQTTClient.DEBUG = True
        self.mqtt_client = MQTTClient(local_config)
        self.valve_controller = ValveController()

    async def _messages(self):  # Respond to incoming messages
        async for topic, msg, retained in self.mqtt_client.queue:
            if topic.startswith('homeassistant/valve/irrigation/'):
                try:
                    command = json.loads(msg)
                except ValueError:
                    command = msg.decode('UTF-8')
                if command == 'OPEN':
                    await self.valve_controller.open()
                elif command == 'CLOSE':
                    await self.valve_controller.close()

    async def _register(self):
        await self.mqtt_client.subscribe('homeassistant/valve/irrigation/#')
        device = {
            "name": "Irrigation",
            "identifiers": [
                "irrigation"
            ]}
        msg = {
            "name": None,
            "device_class": "water",
            "reports_position": "false",
            "state_topic": "homeassistant/valve/irrigation/state",
            "command_topic": "homeassistant/valve/irrigation/set",
            "unique_id": "irrigation_01",
            "expire_after": 120,
            "suggested_area": "Garden",
            "device": device
        }
        await self.mqtt_client.publish("homeassistant/valve/irrigation/config", json.dumps(msg))

    async def _up(self):  # Respond to connectivity being (re)established
        while True:
            await self.mqtt_client.up.wait()  # Wait on an Event
            self.mqtt_client.up.clear()
            await self._register()
            await asyncio.sleep(10)

    async def _down(self):
        while True:
            await self.mqtt_client.down.wait()  # Pause until outage
            self.mqtt_client.down.clear()
            print('WiFi or broker is down.')

    async def start(self):
        await self.mqtt_client.connect()

        for coroutine in (self._up, self._messages):
            asyncio.create_task(coroutine())

    async def stop(self):
        await self.mqtt_client.close()


if __name__ == '__main__':
    c = IrrigationMQTTClient()
    asyncio.run(c.start())

"""    client.subscribe("#")
    print(f"connected, {reason_code}")
    device = {
        "name": "Living Room Sensor Hub",
        "identifiers": [
            "rpico co2"
        ]}
    msg = {
        "name": None,
        "device_class": "carbon_dioxide",
        "unit_of_measurement": "ppm",
        "state_topic": "homeassistant/sensor/living-room/state",
        "unique_id": "co2lr",
        "value_template": "{{ value_json.co2 | round(0) }}",
        "expire_after": 120,
        "suggested_area": "Woonkamer",
        "suggested_display_precision": 0,
        " state_class": "measurement",
        "device": device
    }
    client.publish("homeassistant/sensor/co2lr/config", json.dumps(msg))
    msg = {
        "name": None,
        "device_class": "temperature",
        "unit_of_measurement": "°C",
        "state_topic": "homeassistant/sensor/living-room/state",
        "unique_id": "templr",
        "value_template": "{{ value_json.temperature | round(1) }}",
        "expire_after": 120,
        "suggested_area": "Woonkamer",
        "suggested_display_precision": 1,
        " state_class": "measurement",
        "device": device
    }
    client.publish("homeassistant/sensor/templr/config", json.dumps(msg))
    msg = {
        "name": None,
        "device_class": "humidity",
        "unit_of_measurement": "%",
        "unique_id": "humlr",
        "value_template": "{{ value_json.humidity | round(1) }}",
        "suggested_display_precision": 1,
        "state_topic": "homeassistant/sensor/living-room/state",
        "expire_after": 120,
        "suggested_area": "Woonkamer",
        "state_class": "measurement",
        "device": device
    }
    client.publish("homeassistant/sensor/humlr/config", json.dumps(msg))
    publish_state = publish_cb(client, "homeassistant/sensor/living-room/state")
    p = Process(target=start_measurements, args=(publish_state, ))
    p.start()"""
