import uasyncio as asyncio
from machine import Pin

from config import local_config
from mqtt.mqtt_as import MQTTClient

led = Pin("LED", Pin.OUT)


async def messages(client):  # Respond to incoming messages
    async for topic, msg, retained in client.queue:
        print((topic, msg, retained))


async def up(client):  # Respond to connectivity being (re)established
    while True:
        await client.up.wait()  # Wait on an Event
        client.up.clear()
        await client.subscribe('homeassistant/waterspout/#', 0)
        # await client.subscribe('')


async def down(client):
    while True:
        await client.down.wait()  # Pause until outage
        client.down.clear()
        print('WiFi or broker is down.')


async def main(client):
    await client.connect()
    for coroutine in (up, messages):
        await asyncio.create_task(coroutine(client))
    n = 0
    while True:
        await asyncio.sleep(5)
        print('publish', n)
        # If WiFi is down the following will pause for the duration.
        await client.publish('result', '{}'.format(n), qos=1)
        n += 1


MQTTClient.DEBUG = True  # Optional: print diagnostic messages
mqtt_client = MQTTClient(local_config)
try:
    asyncio.run(main(mqtt_client))
finally:
    mqtt_client.close()
