import uasyncio as asyncio
from machine import Pin


CLOSED = 0
OPENING = 1
OPEN = 2
CLOSING = 3


class ValveController:
    def __init__(self):
        self.controller_pin = Pin(0, mode=Pin.OUT)
        self.led = Pin("LED", mode=Pin.OUT)
        self.open_task = None
        self.status = CLOSED

    async def _open(self, timeout):
        self.status = OPENING
        self.open_task = asyncio.current_task()
        self.controller_pin.on()
        self.led.on()
        self.status = OPEN
        await asyncio.sleep(timeout)
        await self.close()
        self.open_task = None

    async def open(self, timeout=60 * 60):
        await asyncio.create_task(self._open(timeout))

    async def close(self):
        self.status = CLOSING
        if self.open_task:
            self.open_task.cancel()
        self.controller_pin.off()
        self.led.off()
        self.status = CLOSED


async def main():
    vc = ValveController()
    await vc.open(10)
    await asyncio.sleep(11)
    await vc.open(5)
    await vc.close()


if __name__ == '__main__':
    asyncio.run(main())
