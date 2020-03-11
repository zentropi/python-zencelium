from typing import Iterable
from aioredis import create_redis
from aioredis import pubsub
from asgiref.sync import async_to_sync

from zentropi import Frame
from zentropi import Kind

from .models import Agent
from .models import Space
from .models import Account
from .util import add_space_to_meta


class SpaceServer(object):
    def __init__(self):
        self.agent_servers = {}

    async def init(self):
        self.publisher = await create_redis('redis://localhost')

    async def agent_server_add(self, agent: Agent, agent_server: 'AgentServer'):
        if agent.uuid in self.agent_servers:
            raise ConnectionError(f'Agent {agent.name} is already connected.')
        self.agent_servers.update({agent.uuid: agent_server})

    async def agent_server_remove(self, agent: Agent):
        if agent.uuid not in self.agent_servers:
            raise KeyError(f'Agent {agent.name} is not connected.')
        del self.agent_servers[agent.uuid]

    async def agent_is_connected(self, agent: Agent):
        return agent.uuid in self.agent_servers

    async def agent_spaces_update(self, agent: Agent, spaces: Iterable[Space]):
        if agent.uuid not in self.agent_servers:
            raise KeyError(f'Agent {agent.name} is not connected.')
        self.agent_servers[agent.uuid].spaces = spaces

    async def agent_join(self, agent: Agent, spaces: Iterable[Space]):
        if agent.uuid not in self.agent_servers:
            raise KeyError(f'Agent {agent.name} is not connected.')
        await self.agent_servers[agent.uuid].join(spaces)

    async def agent_leave(self, agent: Agent, spaces: Iterable[Space]):
        if agent.uuid not in self.agent_servers:
            raise KeyError(f'Agent {agent.name} is not connected.')
        await self.agent_servers[agent.uuid].leave(spaces)

    async def agent_close(self, agent: Agent):
        if agent.uuid not in self.agent_servers:
            raise KeyError(f'Agent {agent.name} is not connected.')
        await self.agent_servers[agent.uuid].stop()

    async def send_to_agent(self, frame: Frame, agent: Agent):
        if agent.uuid not in self.agent_servers:
            raise KeyError(f'Agent {agent.name} is not connected?')
        await self.publisher.publish(agent.uuid, frame.to_json())

    async def send_to_space(self, frame: Frame, space: Space):
        add_space_to_meta(
            frame, 
            space_name=space.name, 
            space_uuid=space.uuid)
        await self.publisher.publish(space.uuid, frame.to_json())

    async def broadcast(self, frame: Frame, spaces: Iterable[Space]):
        for space in spaces:
            await self.send_to_space(frame, space)


space_server = SpaceServer()
