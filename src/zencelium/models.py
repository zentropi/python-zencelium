import logging
from base64 import b64encode
from datetime import datetime
from hashlib import sha256
from uuid import uuid4

import peewee as pw
from bcrypt import checkpw
from bcrypt import hashpw
from bcrypt import gensalt


logger = logging.getLogger(__name__)
db_proxy = pw.DatabaseProxy()


def generate_uuid():
    return uuid4().hex


def db_init(path):
    db = pw.SqliteDatabase(path, pragmas=(
        ('cache_size', -1024 * 64),
        ('journal_mode', 'wal'),
        ('foreign_keys', 1)))
    db_proxy.initialize(db)
    db.connect()
    db.create_tables([
        Account, 
        Space, 
        Agent, 
        AgentSpace, 
    ])
    return db


class Model(pw.Model):
    uuid = pw.CharField(
        index=True,
        unique=True,
        primary_key=True,
        default=generate_uuid)
    created_at = pw.DateTimeField(default=datetime.utcnow)
    modified_at = pw.DateTimeField()

    def save(self, *args, **kwargs):
        self.modified_at = datetime.utcnow()
        super().save(*args, **kwargs)

    class Meta:
        database = db_proxy


class Account(Model):
    name = pw.CharField(index=True, unique=True)
    display_name = pw.CharField()
    password = pw.CharField()
    last_login = pw.DateTimeField(default=datetime.utcnow)

    @staticmethod
    def _encode_password(password) -> bytes:
        return b64encode(sha256(password.encode('utf-8')).digest())

    @staticmethod
    def _check_password(account_password, given_password) -> bool:
        account_password_bytes = account_password.encode('utf-8')
        given_password_encoded = Account._encode_password(given_password)
        return checkpw(given_password_encoded, account_password_bytes)

    @staticmethod
    def create_account(name: str, password: str, display_name: str = '') -> 'Account':
        encoded_password = Account._encode_password(password)
        hashed_password = hashpw(encoded_password, gensalt())
        account = Account.create(
            name=name,
            display_name=display_name or name,
            password=hashed_password)
        logger.critical(f'Account created: {account.name}')
        account_agent = account.create_agent(name)
        account_space = account.create_space(name)
        return account

    def account_agent(self):
        return Agent.get(name=self.name, account=self)

    def account_space(self):
        return Space.get(name=self.name, account=self)

    @staticmethod
    def delete_account(name: str) -> None:
        account = Account.get(name=name)
        account.delete_instance()

    @staticmethod
    def login_account(name: str, password: str) -> 'Account':
        account = Account.get_or_none(name=name)
        if account is None:
            raise PermissionError(f'Login failed for {name}')
        if Account._check_password(account.password, password):
            account.last_login = datetime.utcnow()
            account.save()
            return account
        raise PermissionError(f'Login failed for {name}')

    def create_space(self, name) -> 'Space':
        space = Space.create(name=name, account=self)
        # self.account_agent().join_space(space.name)
        return space

    def delete_space(self, name) -> None:
        space = Space.get_or_none(name=name, account=self)
        # self.account_agent().leave_space(space.name)
        if space is None:
            raise PermissionError(f'Cannot delete space {name!r} for account {self.name!r}')
        space.delete_instance()

    def create_agent(self, name) -> 'Agent':
        return Agent.create(name=name, account=self)

    def delete_agent(self, name) -> None:
        agent = Agent.get_or_none(name=name, account=self)
        if agent is None:
            raise PermissionError(f'Cannot delete agent {name!r} for account {self.name!r}, does the agent exist?')
        agent.delete_instance()


class Space(Model):
    name = pw.CharField(index=True)
    account = pw.ForeignKeyField(Account, on_delete='CASCADE', backref='spaces')

    class Meta:
        indexes = (
            (('name', 'account'), True),  # names are unique for account
        )

    def agents(self) -> pw.Query:
        query = (Agent
            .select()
            .join(AgentSpace)
            .join(Space)
            .where(Space.name == self.name)
        )
        return query


class Agent(Model):
    name = pw.CharField(index=True)
    account = pw.ForeignKeyField(Account, on_delete='CASCADE', backref='agents')
    token = pw.CharField(index=True, default=generate_uuid)

    class Meta:
        indexes = (
            (('name', 'account'), True),  # names are unique for account
        )

    def join_space(self, name) -> Space:
        space = Space.get_or_none(name=name, account=self.account)
        if space is None:
            raise PermissionError(f'Agent {self.name!r} cannot join space {name!r} for account {self.account.name!r}, does the space exist?')
        AgentSpace.get_or_create(agent=self, space=space)
        return space

    def leave_space(self, name) -> Space:
        space = Space.get_or_none(name=name, account=self.account)
        if space is None:
            raise PermissionError(f'Agent {self.name!r} cannot leave space {name!r} for account {self.account.name!r}, does the space exist?')
        agent_space = AgentSpace.get_or_none(agent=self, space=space)
        if agent_space is None:
            raise KeyError(f'Agent {self.name!r} has not joined space {name!r} for account {self.account.name!r}')
        agent_space.delete_instance()
        return space

    def spaces(self) -> pw.Query:
        query = (Space
            .select()
            .join(AgentSpace)
            .join(Agent)
            .where(Agent.name == self.name)
            )
        return query


class AgentSpace(Model):
    agent = pw.ForeignKeyField(Agent, on_delete='CASCADE')
    space = pw.ForeignKeyField(Space, on_delete='CASCADE')
