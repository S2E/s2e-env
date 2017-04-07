import os

import yaml

from s2e_env.utils.memoize import memoize


# Paths
YAML_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'dat',
                                'config.yaml')


@memoize
def _load_constants():
    with open(YAML_CONFIG_PATH, 'r') as f:
        return yaml.load(f)


CONSTANTS = _load_constants()
