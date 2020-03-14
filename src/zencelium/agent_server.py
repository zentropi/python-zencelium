import asyncio
import logging
from uuid import uuid4
from typing import Iterable

from aioredis import create_redis
from aioredis import pubsub
from asgiref.sync import async_to_sync
from quart import session

from zentropi import KB
from zentropi import Frame
from zentropi import Kind

from .models import Agent
from .models import Space
from .models import Account
from .space_server import space_server
from .util import add_space_to_meta
from .util import timestamp

logger = logging.getLogger(__name__)


def on_event(_name):
    def wrap(func):
        setattr(func, 'handle_event', _name)
        return func
    return wrap


def on_command(_name):
    def wrap(func):
        setattr(func, 'handle_command', _name)
        return func
    return wrap


def on_message(_name):
    def wrap(func):
        setattr(func, 'handle_message', _name)
        return func
    return wrap


class AgentServer(object):
    def __init__(self, websocket):
        self.websocket = websocket
        self.account = None  # set by login()
        self.agent = None  # set by login()
        self.spaces = set()  # set by login(), join() and leave()
        self.receiver = pubsub.Receiver()
        self.redis = None
        self.connected = False
        self.receive_loops = tuple()  # set by start()
        self._handlers_command = {}
        self._handlers_event = {}
        self._handlers_message = {}
        self.space_server = space_server
        self._filter_event_names = {'*'}
        self._filter_message_names = {'*'}
        self.load_handlers()
        self._frame_max_size = 1 * KB

    def load_handlers(self):
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if not callable(attr):
                continue
            if getattr(attr, 'handle_event', None):
                self._handlers_event[getattr(attr, 'handle_event')] = attr
            elif getattr(attr, 'handle_command', None):
                self._handlers_command[getattr(attr, 'handle_command')] = attr
            elif getattr(attr, 'handle_message', None):
                self._handlers_message[getattr(attr, 'handle_message')] = attr

    async def start(self):
        self.connected = True
        self.redis = await create_redis('redis://localhost')
        try:
            await self._session_login()
            ws_recv_loop = asyncio.create_task(self.websocket_recv())
            bc_recv_loop = asyncio.create_task(self.broadcast_recv())
            self.receive_loops = (ws_recv_loop, bc_recv_loop)
            await asyncio.gather(*self.receive_loops)
        except Exception as e:
            await self.stop()
            raise e
        finally:
            if self.agent:
                await space_server.agent_server_remove(self.agent)
            self.redis.close()
            await self.redis.wait_closed()

    async def stop(self):
        for task in self.receive_loops:
            task.cancel()

    async def frame_handler(self, frame) -> None:
        kind = frame.kind
        name = frame.name
        if kind == Kind.COMMAND:
            if name in self._handlers_command:
                handler = self._handlers_command[name]
            elif '*' in self._handlers_command:
                handler = self._handlers_command['*']
            else:
                return
        elif kind == Kind.EVENT:
            if name in self._handlers_event:
                handler = self._handlers_event[name]
            elif '*' in self._handlers_event:
                handler = self._handlers_event['*']
            else:
                return
        elif kind == Kind.MESSAGE:
            if name in self._handlers_message:
                handler = self._handlers_message[name]
            elif '*' in self._handlers_message:
                handler = self._handlers_message['*']
            else:
                return
        else:
            raise KeyError(f'Unknown kind {kind} in {name}')
        await handler(frame)

    async def websocket_recv(self):
        while self.connected:
            frame = Frame.from_json(await self.websocket.receive())
            await self.frame_handler(frame)

    async def websocket_send(self, frame: Frame):
        await self.websocket.send(frame.to_json())

    async def broadcast_recv(self):
        spaces = self.receiver
        while await spaces.wait_message():
            _, frame_as_json = await spaces.get(encoding='utf-8')
            frame = Frame.from_json(frame_as_json)
            if self._frame_max_size <= 256:
                frame._uuid = ''
                frame._meta = {}
                frame_as_json = frame.to_json()
                logger.info(f'Strip uuid and meta from frame as agent {self.agent.name} requested small frames.')
            if len(frame_as_json) > self._frame_max_size:
                logger.info(f'Skip frame: {frame.name} for agent {self.agent.name} as size ({len(frame_as_json)}) is larger than {self._frame_max_size} bytes.')
                continue
            if frame.kind == Kind.EVENT:
                if '*' in self._filter_event_names:
                    await self.websocket_send(frame)
                    continue
                elif frame.name in self._filter_event_names:
                    await self.websocket_send(frame)
                    continue
            elif frame.kind == Kind.MESSAGE:
                if '*' in self._filter_message_names:
                    await self.websocket_send(frame)
                    continue
                elif frame.name in self._filter_message_names:
                    await self.websocket_send(frame)
                    continue
            logger.info(f'Skipping frame: {frame.name} for agent {self.agent.name}')

    async def broadcast_send(self, frame: Frame, spaces: Iterable[Space]):
        meta = {'source': {
                'name': self.agent.name,
                # 'uuid': self.agent.uuid,
            },
            'timestamp': timestamp(),
        }
        if frame.meta:
            frame._meta.update(meta)
        else:
            frame._meta = meta
        if not spaces:
            logger.warning(f'No spaces for broadcast for agent {self.agent.name}')
        await self.space_server.broadcast(frame, spaces=spaces)

    async def _session_login(self):
        logged_in = session.get("logged_in")
        account_name = session.get("account_name")
        if logged_in:
            logger.info(f'*** session-account: {account_name}')
            account = Account.get(name=account_name)
            agent = account.account_agent()
            self.agent = agent
            self.account = account
            await self.login(token=agent.token)
            frame = Frame('login-ok', kind=Kind.COMMAND)
            add_space_to_meta(frame, 'server', 'server')
            await self.websocket_send(frame)

    async def login(self, token):
        agent = Agent.get_or_none(token=token)
        if agent:
            self.agent = agent
            # self.spaces = set(agent.spaces())
            await space_server.agent_server_add(agent, self)
            channels = [self.receiver.channel(agent.uuid)]
            await self.redis.subscribe(*channels)
        return agent

    async def join(self, spaces: Iterable[Space]):
        if not spaces:
            logger.debug(f'No spaces to join for agent {self.agent}')
            return
        channels = []
        for space in spaces:
            self.spaces.add(space)
            channels.append(self.receiver.channel(space.uuid))
        await self.redis.subscribe(*channels)

    async def leave(self, spaces: Iterable[Space]):
        if not spaces:
            logger.debug(f'No spaces to leave for agent {self.agent}')
            return
        channels = []
        for space in spaces:
            self.spaces.remove(space)
            channels.append(self.receiver.channel(space.uuid))
        if channels:
            await self.redis.unsubscribe(*channels)

    @on_command('login')
    async def cmd_login(self, frame: Frame):
        token = frame.data.get('token')
        agent = await self.login(token)
        if not token or not agent:
            await self.websocket_send(frame.reply('login-failed'))
            logger.info(f'Login failed for {frame.data}')
            await self.stop()
            return
        self.account = agent.account
        reply = frame.reply('login-ok')
        add_space_to_meta(reply, 'server', 'server')
        await self.websocket_send(reply)
        logger.info(f'Logged in agent {agent.name} for account {self.account.name}')

    def _clean_space_names(self, obj: dict):
        space_names = obj.get('spaces')
        if not space_names:
            return []
        if isinstance(space_names, str):
            space_names = [s.strip() for s in space_names.split(',')]
        else:
            space_names = list(space_names)
        return space_names

    def _get_spaces_from_names(self, space_names):
        spaces = (Space.select()
            .where(
                Space.name.in_(space_names),
                Space.account == self.account
            ))
        return spaces

    @on_command('join')
    async def cmd_join(self, frame: Frame):
        space_names = self._clean_space_names(frame.data)
        spaces = self._get_spaces_from_names(space_names)
        if '*' in space_names:
            spaces = list(self.agent.spaces())
        else:
            spaces = self._get_spaces_from_names(space_names)
        await self.join(spaces)
        reply = frame.reply('join-ok')
        add_space_to_meta(reply, 'server', 'server')
        await self.websocket_send(reply)

    @on_command('leave')
    async def cmd_leave(self, frame: Frame):
        space_names = self._clean_space_names(frame.data)
        if '*' in space_names:
            spaces = self.spaces
        else:
            spaces = self._get_spaces_from_names(space_names)
        await self.leave(spaces)
        await self.websocket_send(frame.reply('leave-ok'))

    @on_command('filter')
    async def cmd_filter(self, frame: Frame):
        if frame.data.get('size'):
            self._frame_max_size = int(frame.data.get('size'))

        if frame.data.get('names'):
            self._filter_event_names = set(frame.data['names'].get('event', []))
            self._filter_message_names = set(frame.data['names'].get('message', []))

        await self.websocket_send(frame.reply('filter-ok'))


    @on_command('*')
    async def cmd_unknown(self, frame: Frame):
        await self.websocket_send(frame.reply('unknown-command', data={'command': frame.name}))

    @on_event('*')
    async def evt_relay(self, frame: Frame):
        spaces = self.spaces
        if frame.meta and frame.meta.get('spaces'):
            space_names = self._clean_space_names(frame.meta)
            spaces = self._get_spaces_from_names(space_names)
        await self.broadcast_send(frame, spaces=spaces)

    @on_message('*')
    async def msg_relay(self, frame: Frame):
        spaces = self.spaces
        if frame.meta and frame.meta.get('spaces'):
            space_names = self._clean_space_names(frame.meta)
            spaces = self._get_spaces_from_names(space_names)
        await self.broadcast_send(frame, spaces=spaces)
