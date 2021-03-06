import aioredis
import os

__redis_pool = None

async def redis_connection():
    global __redis_pool

    if not __redis_pool:
        __redis_pool = await aioredis.create_redis_pool('redis://%s' % os.environ['REDIS_HOST'])

    return __redis_pool
