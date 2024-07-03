import uasyncio as asyncio

from config import local_config
from mqtt.mqtt_as import MQTTClient


class Device():
    def __init__(self):
        self.valve = Valve()
        self.flow_sensor = FlowSensor()


async def main(client):
    pass


if __name__ == '__main__':
    MQTTClient.DEBUG = True  # Optional: print diagnostic messages
    mqtt_client = MQTTClient(local_config)
    try:
        asyncio.run(main(mqtt_client))
    finally:
        mqtt_client.close()
