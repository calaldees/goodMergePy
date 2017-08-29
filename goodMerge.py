import os.path
import json
import xml.dom.minidom
from functools import reduce
import logging

log = logging.getLogger(__name__)


# Constants --------------------------------------------------------------------
VERSION = 'v0.0.0'
DESCRIPTION = """
"""
DEFAULT_CONFIG_FILENAME = 'config.json'


# Command Line Arguments -------------------------------------------------------

def get_args():
    import argparse

    parser = argparse.ArgumentParser(
        prog=__name__,
        description=DESCRIPTION,
    )

    parser.add_argument('--config', action='store', help='', default=DEFAULT_CONFIG_FILENAME)
    parser.add_argument('--postmortem', action='store_true', help='Enter debugger on exception')
    parser.add_argument('--log_level', type=int, help='log level')
    parser.add_argument('--version', action='version', version=VERSION)

    kwargs = vars(parser.parse_args())

    # Overlay config defaults from file
    if os.path.isfile(kwargs['config']):
        with open(kwargs['config'], 'rt') as config_filehandle:
            config = json.load(config_filehandle)
            kwargs = {k: v if v is not None else config.get(k) for k, v in kwargs.items()}
            kwargs.update({k: v for k, v in config.items() if k not in kwargs})
    else:
        log.warn(f'''Config does not exist {kwargs['config']}''')

    return kwargs


# Main -------------------------------------------------------------------------

def main(**kwargs):
    with open('./var/xmdb/GoodGBA.xmdb', 'rt') as filehandle:
        data = xml.dom.minidom.parse(filehandle)

    # Parse 'Zones' - These associate esoteric names with the primary set
    def parse_zone(acc, zone):
        if zone.childNodes[0].nodeType != zone.ELEMENT_NODE:
            log.debug(f'wtf is this {zone}')
            return acc
        acc[zone.childNodes[0].getAttribute('name')] = tuple(
            zone_child.getAttribute('name')
            for zone_child in zone.childNodes[1:]
            if zone_child.nodeType == zone_child.ELEMENT_NODE
        )
        return acc
    zones = reduce(parse_zone , data.getElementsByTagName('zoned'), {})

    assert False


def postmortem(func, *args, **kwargs):
    import traceback
    import pdb
    import sys
    try:
        return func(*args, **kwargs)
    except Exception:
        type, value, tb = sys.exc_info()
        traceback.print_exc()
        pdb.post_mortem(tb)


if __name__ == "__main__":
    kwargs = get_args()
    logging.basicConfig(level=kwargs['log_level'])

    def launch():
        main(**kwargs)
    if kwargs.get('postmortem'):
        postmortem(launch)
    else:
        launch()
