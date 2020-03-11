import asyncio
import logging
from functools import wraps
from signal import SIGTERM
from signal import SIGINT

from peewee import IntegrityError
from hypercorn.asyncio import serve as hypercorn_serve
from hypercorn.config import Config as HypercornConfig
from quart import Quart
from quart import abort as abort_request
from quart import flash as flash_message
from quart import jsonify
from quart import request
from quart import redirect
from quart import render_template
from quart import session
from quart import url_for
from quart import websocket

from zentropi import Frame
from zentropi import Kind

from .agent_server import AgentServer
from .models import Account
from .models import Agent
from .models import Space
from .models import db_init

logger = logging.getLogger(__name__)

app = Quart('zencelium')
app.jinja_env.line_statement_prefix = '@'
app.jinja_env.line_comment_prefix = '##'
app.secret_key = 'uPqa6poW2hd5e3bKLcYrzDcNzaSV85ymWCAkyPgMA3'
from .space_server import space_server


def login_required(fn):
    @wraps(fn)
    async def inner(*args, **kwargs):
        if session.get('logged_in'):
            account_name = session.get('account_name')
            account = Account.get(name=account_name)
            return await fn(account=account, *args, **kwargs)
        return redirect(url_for('login', next=request.path))

    return inner


@app.before_serving
async def startup():
    db_init('zencelium.db')
    logger.info('Starting web server')
    await space_server.init()


@app.after_serving
def shutdown():
    logger.info('Shutting down web server')


@app.route('/')
async def index():
    return await render_template('index.html')


@app.route('/register/', methods=['GET', 'POST'])
async def register():
    form = await request.form
    if request.method == 'POST':
        name = str(form.get('name'))
        display_name = str(form.get('display_name'))
        password = str(form.get('password'))
        if not name or not password:
            await flash_message(f'Account name and password are required.')
            return await render_template(
                'register.html',
                name=name, display_name=display_name)
        try:
            account = Account.create_account(
                name=name,
                display_name=display_name,
                password=password)
            account = Account.login_account(name, password)
            session['logged_in'] = True
            session['account_name'] = name
            session.permanent = True
            await flash_message(f'Registered account {name!r} and logged in.')
            return redirect(url_for('index'))
        except IntegrityError:
            await flash_message(f'Unable to register account {name}, please choose another account name.')
            return await render_template(
                'register.html', name=name, display_name=display_name)
    return await render_template('register.html')


@app.route('/login/', methods=['GET', 'POST'])
async def login():
    form = await request.form
    if request.method == 'POST' and form.get('name') and form.get('password'):
        name = str(form.get('name'))
        password = str(form.get('password'))
        try:
            account = Account.login_account(name, password)
            session['logged_in'] = True
            session['account_name'] = name
            session.permanent = True
            await flash_message(f'Welcome {account.display_name}')
            return redirect(url_for('index'))
        except Exception as e:
            logger.exception(e)
            await flash_message(f'Unable to login {name!r}')
            return await render_template(
                'login.html', name=name)
    return await render_template('login.html')


@app.route('/logout/', methods=['GET', 'POST'])
@login_required
async def logout(account):
    if request.method == 'POST':
        session.clear()
        await flash_message('You have logged out.', 'success')
        return redirect(url_for('index'))
    return await render_template('logout.html')


@app.route('/agents/', methods=['GET', 'POST'])
@login_required
async def agents(account):
    if request.method == 'POST':
        form = await request.form
        name = form.get('name')
        try:
            agent = account.create_agent(name)
            await flash_message(f'Agent {name!r} created.', 'success')
            return redirect(url_for('agent_detail', name=name))
        except Exception as e:
            logger.exception(e)
            await flash_message(f'Agent {name!r} was not created.', 'danger')
    agents = account.agents
    return await render_template(
        'agents.html', agents=agents)


@app.route('/agents/<name>/', methods=['GET', 'POST'])
@login_required
async def agent_detail(account, name):
    try:
        agent = Agent.get(name=name)
        unjoined_spaces = set(account.spaces) - set(agent.spaces())
        return await render_template(
            'agent_detail.html', agent=agent, unjoined_spaces=unjoined_spaces)
    except Exception as e:
        logger.exception(e)
        await flash_message(f'Agent {name!r} was not found.', 'danger')
        return redirect(url_for('agents'))


@app.route('/agents/<name>/delete/', methods=['POST'])
@login_required
async def agent_delete(account, name):
    try:
        agent = Agent.get(name=name)
        if await space_server.agent_is_connected(agent):
            print(f'Closing active connection for {agent.name}')
            await space_server.agent_close(agent)
        account.delete_agent(name)
        await flash_message(f'Agent {name!r} deleted.', 'success')
        return redirect(url_for('agents'))
    except Exception as e:
        logger.exception(e)
        await flash_message(f'Agent {name!r} was not deleted. {e}', 'danger')
        return redirect(url_for('agent_detail', name=name))


@app.route('/agents/<name>/join/', methods=['POST'])
@login_required
async def agent_join(account, name):
    form = await request.form
    agent_name = form.get('agent_name')
    space_name = form.get('space_name')
    try:
        agent = Agent.get(name=name)
        agent.join_space(space_name)
        spaces = list(agent.spaces())
        try:
            await space_server.agent_spaces_update(agent, spaces)
        except KeyError:
            pass
        try:
            await space_server.agent_join(agent, spaces)
        except KeyError:
            pass
        await flash_message(f'Agent {agent_name!r} joined {space_name!r}.', 'success')
    except Exception as e:
        logger.exception(e)
        await flash_message(f'Agent {agent_name!r} could not join {space_name!r}.', 'danger')
    finally:
        return redirect(url_for('agent_detail', name=name))


@app.route('/agents/<name>/leave/', methods=['POST'])
@login_required
async def agent_leave(account, name):
    form = await request.form
    agent_name = form.get('agent_name')
    space_name = form.get('space_name')
    try:
        agent = Agent.get(name=agent_name)
        leave_space = agent.leave_space(space_name)
        try:
            await space_server.agent_leave(agent, [leave_space])
        except KeyError:
            pass
        await flash_message(f'Agent {agent_name!r} left {space_name!r}.', 'success')
    except Exception as e:
        logger.exception(e)
        await flash_message(f'Agent {agent_name!r} could not leave {space_name!r}.', 'danger')
    finally:
        return redirect(url_for('agent_detail', name=name))


@app.route('/spaces/', methods=['GET', 'POST'])
@login_required
async def spaces(account):
    if request.method == 'POST':
        form = await request.form
        name = form.get('name')
        try:
            space = account.create_space(name)
            agent = account.account_agent()
            agent.join_space(space.name)
            try:
                await space_server.agent_spaces_update(agent, [space])
            except KeyError:
                pass
            try:
                await space_server.agent_join(agent, [space])
            except KeyError:
                pass
            await flash_message(f'Space {name!r} created.', 'success')
            return redirect(url_for('space_detail', name=name))
        except Exception as e:
            logger.exception(e)
            await flash_message(f'Space {name!r} was not created.', 'danger')
    spaces = account.spaces
    return await render_template(
        'spaces.html', spaces=spaces)


@app.route('/spaces/<name>/', methods=['GET', 'POST'])
@login_required
async def space_detail(account, name):
    try:
        space = Space.get(name=name)
        unjoined_agents = set(account.agents) - set(space.agents())
        return await render_template(
            'space_detail.html', space=space, unjoined_agents=unjoined_agents)
    except Exception as e:
        logger.exception(e)
        await flash_message(f'Space {name!r} was not found.', 'danger')
        return redirect(url_for('spaces'))


@app.route('/spaces/<name>/delete/', methods=['POST'])
@login_required
async def space_delete(account, name):
    try:
        agent = account.account_agent()
        try:
            leave_space = agent.leave_space(name)
            try:
                await space_server.agent_leave(agent, [leave_space])
            except KeyError:
                pass
        except KeyError:
            pass
        account.delete_space(name)
        await flash_message(f'Space {name!r} deleted.', 'success')
        return redirect(url_for('spaces'))
    except Exception as e:
        logger.exception(e)
        await flash_message(f'Space {name!r} was not deleted. {e}', 'danger')
        return redirect(url_for('space_detail', name=name))


@app.route('/spaces/<name>/join/', methods=['POST'])
@login_required
async def space_join(account, name):
    form = await request.form
    agent_name = form.get('agent_name')
    space_name = form.get('space_name')
    try:
        agent = Agent.get(name=agent_name)
        agent.join_space(space_name)
        spaces = list(agent.spaces())
        try:
            await space_server.agent_spaces_update(agent, spaces)
        except KeyError:
            pass
        try:
            await space_server.agent_join(agent, spaces)
        except KeyError:
            pass
        await flash_message(f'Agent {agent_name!r} joined {space_name!r}.', 'success')
    except Exception as e:
        logger.exception(e)
        await flash_message(f'Agent {agent_name!r} could not join {space_name!r}.', 'danger')
    finally:
        return redirect(url_for('space_detail', name=name))


@app.route('/spaces/<name>/leave/', methods=['POST'])
@login_required
async def space_leave(account, name):
    form = await request.form
    agent_name = form.get('agent_name')
    space_name = form.get('space_name')
    try:
        agent = Agent.get(name=agent_name)
        leave_space = agent.leave_space(space_name)
        try:
            await space_server.agent_leave(agent, [leave_space])
        except KeyError:
            pass
        await flash_message(f'Agent {agent_name!r} left {space_name!r}.', 'success')
    except Exception as e:
        logger.exception(e)
        await flash_message(f'Agent {agent_name!r} could not leave {space_name!r}.', 'danger')
    finally:
        return redirect(url_for('space_detail', name=name))


@app.route('/console/')
@login_required
async def console(account):
    agent = account.account_agent()
    return await render_template(
        'console.html', 
        agent_token=agent.token,
        agent_spaces=agent.spaces())


@app.websocket('/')
async def agent_websocket():
    agent_server = AgentServer(websocket)
    await agent_server.start()


def run(bind, port):
    shutdown_event = asyncio.Event()


    def _signal_handler(*_):
        shutdown_event.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(SIGTERM, _signal_handler)
    loop.add_signal_handler(SIGINT, _signal_handler)

    config = HypercornConfig()

    config.bind = [f'{bind}:{port}']

    loop.run_until_complete(hypercorn_serve(
        app, config, shutdown_trigger=shutdown_event.wait))
