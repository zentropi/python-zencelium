"""
Module that contains the command line app.

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -mzencelium` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``zencelium.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``zencelium.__main__`` in ``sys.modules``.

  Also see (1) from http://click.pocoo.org/5/setuptools/#setuptools-integration
"""
import click
from .web import run

@click.group()
def cli():
    pass


@cli.command('run')
@click.option('--bind', default='127.0.0.1')
@click.option('--port', default=26514, type=int)
def cli_run(bind, port):
    run(bind=bind, port=port)
