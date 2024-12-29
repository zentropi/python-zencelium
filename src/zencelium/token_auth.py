from functools import wraps

from quart import g
from quart import request
from werkzeug.exceptions import Unauthorized

from .models import Agent


class AgentTokenAuth(object):
    def __init__(self, app):
        self.app = app
        self.app.before_request(self.authenticate)

    async def authenticate(self):
        if "Authorization" in request.headers:
            token = request.headers.get("Authorization").replace("Bearer ", "")
            try:
                agent = Agent.get_or_none(token=token)
                if agent:
                    g.agent = agent
            except:
                raise Unauthorized()

    def login_required(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not getattr(g, "agent", None):
                raise Unauthorized()
            else:
                agent = g.agent
                return await func(agent=agent, *args, **kwargs)

        return wrapper
