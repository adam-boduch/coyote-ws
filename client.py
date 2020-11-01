import logging
from fastapi import WebSocket
from utils.redis import redis_connection
from utils.crypt import jwt_decode
from utils.types import ChannelNames
from utils.json import is_valid_json
from aioredis.pubsub import Receiver
from json import dumps
import asyncio
import aioredis
import os

class Client:
    def __init__(self, websocket: WebSocket):
        self._websocket = websocket
        self._redis = None
        self._allowed_channels: ChannelNames = set()
        self._channels: ChannelNames = set()
        self._receiver = Receiver()

    def __del__(self):
        logging.info('Closing connection')

        self._redis.close()
        self._redis = None

    async def authorize(self, token: str):
        try:
            self._allowed_channels = jwt_decode(token)

            logging.info('Client authenticated. Allowed channels: %s' % self._allowed_channels)

            self._redis = await aioredis.create_redis((os.environ['REDIS_HOST'], 6379))
        except Exception as e:
            logging.warning('Invalid token: %s. Error: %s.' % (token, str(e)))

            await self._websocket.close(403)

    async def handle_message(self, message: str):
        if message[0:9] == 'subscribe':
            await self.unsubscribe()

            channel_name = message[10:]
            self._channels.add(channel_name)

            await self.subscribe()

        if not (data := is_valid_json(message)):
            return

        channel_name = data.get('channel')

        await self.publish(channel_name, dumps(data))

    async def publish(self, channel_name: str, data: str):
        pub_connection = await redis_connection()

        await pub_connection.publish(channel_name, data)

    async def subscribe(self):
        """
        Subscribe to Redis channel and if - event occurs - pass data to the client by calling websocket method

        :return:
        """
        async def reader():
            async for channel, message in self._receiver.iter():
                logging.info(message)

                await self._websocket.send_text(message.decode('utf-8'))

        asyncio.ensure_future(reader())

        await self._redis.subscribe(
            *[self._receiver.channel(channel) for channel in self._channels]
        )

        logging.info('Subscribed channels: %s' % self._channels)

    async def unsubscribe(self):
        if self._channels:
            await self._redis.unsubscribe(*self._channels)

        # self._channels = []

        logging.info('Unsubscribed')