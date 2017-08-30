import os
import re
import json
import xml.dom.minidom
from functools import reduce
from collections import defaultdict
import logging

log = logging.getLogger(__name__)


# Constants --------------------------------------------------------------------
VERSION = 'v0.0.0'
DESCRIPTION = """
"""
DEFAULT_CONFIG_FILENAME = 'config.json'

#REGEX_XMDB_TYPE = re.compile(r'Good(.*)\.xmdb', flags=re.IGNORECASE)
TEMPLATE_FILENAME_XMDB = 'Good{}.xmdb'


# Command Line Arguments -------------------------------------------------------

def get_args():
    import argparse

    parser = argparse.ArgumentParser(
        prog=__name__,
        description=DESCRIPTION,
    )

    parser.add_argument('type', action='store', help='')
    parser.add_argument('--path_xmdb', action='store', help='')
    parser.add_argument('--path_roms', action='store', help='')
    parser.add_argument('--path_filelist', action='store', help='for debugging')

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

    #def get_type_from_filename(filename):
    #    match = REGEX_XMDB_TYPE.match(filename)
    #    if match:
    #        return match.group(1).lower()
    #types = set(filter(None, map(get_type_from_filename, os.listdir(kwargs['path_xmdb']))))
    #assert kwargs['type'] in types, f'type must be one of {types}'

    return kwargs


# Main -------------------------------------------------------------------------

def main(**kwargs):
    # Read XMDB data
    filename = os.path.join(kwargs['path_xmdb'], TEMPLATE_FILENAME_XMDB.format(kwargs['type']))
    assert os.path.isfile(filename), f'{filename} does not exist'
    with open(filename, 'rt') as filehandle:
        data = xml.dom.minidom.parse(filehandle)

    # Read filelist
    if kwargs.get('path_filelist'):
        with open(kwargs['path_filelist'], 'rt') as filehandle:
            filelist = filehandle.read().split('\n')
    else:
        filelist = os.listdir(kwargs.get('path_roms') or './')
    log.info(f'{len(filelist)} in filelist')

    def group_filelist(acc, filename):
        normalized_filename = re.match(r'[^(.[]*', filename).group(0).strip()
        acc[normalized_filename].add(filename)
        return acc
    grouped_filelist = reduce(group_filelist, filelist, defaultdict(set))

    # Parse 'Zones' - These associate esoteric names with the primary set
    def parse_zone(acc, zone):
        if zone.childNodes[0].nodeType != zone.ELEMENT_NODE:
            log.warn(f'wtf is this {zone}')
            return acc
        parent_name = zone.childNodes[0].getAttribute('name')
        #log.debug(f'parent: {parent_name}')
        #acc[parent_name] = tuple(
        #    zone_child.getAttribute('name')
        #    for zone_child in zone.childNodes[1:]
        #    if zone_child.nodeType == zone_child.ELEMENT_NODE
        #)
        for zone_child in for zone_child in zone.childNodes[1:]:
            if zone_child.nodeType == zone_child.ELEMENT_NODE:
                child_name = zone_child.getAttribute('name')
                #acc[parent_name] += acc[child_name]
                #del acc[child_name]
        return acc
    zones = reduce(parse_zone, data.getElementsByTagName('zoned'), grouped_filelist)

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
