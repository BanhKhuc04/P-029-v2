from copy import deepcopy
import pytest
from pointsnap.core.config import ConfigError,load_config,parse_config


@pytest.mark.parametrize('kind', ['scalar', 'range'])
def test_unrepresentable_yaml_integer_is_a_config_error(kind):
    data = deepcopy(load_config(env={}).to_dict(redact=False))
    data['cvat'].pop('token', None)
    if kind == 'scalar':
        data['floating']['ring_inner_m'] = 10**1000
    else:
        data['size']['manual_ranges'] = {'car': {'length': [1, 10**1000], 'width': [1, 2], 'height': [1, 2]}}
    with pytest.raises(ConfigError):
        parse_config(data, env={})
