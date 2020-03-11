import logging
from configparser import ConfigParser
from pathlib import Path
from os import makedirs as make_directories
from sys import intern

logger = logging.getLogger(__name__)


class BaseConfig(object):
    def __init__(self, config_path, app_name) -> None:
        self._config_path = Path(config_path)
        self._config = ConfigParser()
        self._app_name = app_name
        self._config[self._app_name]= {}

    def init(self):
        self._load_defaults()
        self._load_fields()
        self._ensure_file()
        self.load()

    def _fields(self):
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if callable(attr):
                continue
            elif attr_name.startswith('_'):
                continue
            logger.debug(f'Loading config field {attr_name}: {attr}')
            yield attr_name, attr

    def _load_defaults(self):
        defaults = {}
        for name, value in self._fields():
            logger.debug(f'Loading default {name} = {value}')
            defaults.update({name:value})
        self._config.read_dict({self._app_name: defaults})

    def _load_fields(self):
        for name, value in self._fields():
            try:
                self._config[self._app_name][name] = value
            except TypeError:
                raise TypeError(f'Expected string value for {name}, got {value!r}')

    def _set_fields(self):
        for name, value in self._fields():
            logger.debug(f'Setting new value {name} = {self._config[self._app_name][name]}')
            setattr(self, name, self._config[self._app_name][name])

    def _ensure_file(self):
        if self._config_path.exists():
            logger.debug(f'Config exists at {self._config_path!r}')
            return
        # self._load_defaults()
        # self._load_fields()
        make_directories(self._config_path.parent, exist_ok=True)
        self.save()

    def load(self):
        logger.info(f'Loading config from {self._config_path!r}')
        self._config.read(self._config_path)
        self._set_fields()

    def save(self):
        self._load_fields()
        logger.info(f'Saving config to {self._config_path!r}')
        with open(self._config_path, 'w', encoding='utf-8') as config_file:
            self._config.write(config_file)


