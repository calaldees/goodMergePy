import os
import re
import json
import xml.dom.minidom
from functools import reduce
from collections import defaultdict
from tempfile import TemporaryDirectory
import shutil
from functools import partial
import subprocess
import logging

log = logging.getLogger(__name__)


# Constants --------------------------------------------------------------------
VERSION = 'v0.0.0'
DESCRIPTION = """
"""
DEFAULT_CONFIG_FILENAME = 'config.json'

#REGEX_XMDB_TYPE = re.compile(r'Good(.*)\.xmdb', flags=re.IGNORECASE)
TEMPLATE_FILENAME_XMDB = 'Good{}.xmdb'


# Utils ------------------------------------------------------------------------

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return sorted(list(obj))
        return json.JSONEncoder.default(self, obj)


def _load_xml(source):
    if os.path.isfile(source):
        with open(source, 'rt') as filehandle:
            return xml.dom.minidom.parse(filehandle)
    else:
        return xml.dom.minidom.parseString(source)


def parse_xmdb_dom(dom):
    """
    Mocking XML objects for tests is tricky.
    Parse an XML structure into our own intermediary data structure

    TODO: Doctest
    """
    def _parse_zone(acc, zone):
        #deferred = bool(zone.getAttribute('deferred'))
        childNodeElements = tuple(filter(lambda node: node.nodeType == node.ELEMENT_NODE, zone.childNodes))
        if not childNodeElements:
            return acc
        parent_name = childNodeElements[0].getAttribute('name')
        def _group_nodes(acc, node):
            if node.nodeType == node.ELEMENT_NODE:
                if node.tagName in ('bias', 'clone') and node.getAttribute('name'):
                    acc['clones'].add(node.getAttribute('name'))
                if node.tagName in ('group'):
                    acc['regex'].add(node.getAttribute('reg'))
            return acc
        acc[parent_name] = reduce(_group_nodes, childNodeElements[1:], {'regex': set(), 'clones': set()})
        return acc

    return {
        'zoned': reduce(_parse_zone, dom.getElementsByTagName('zoned'), {})
    }


def get_filelist(path_roms=None, path_filelist=None):
    assert bool(path_roms) ^ bool(path_filelist), 'path_roms or path_filelist'
    # Read filelist
    if path_filelist and os.path.isfile(path_filelist):
        with open(path_filelist, 'rt') as filehandle:
            return filehandle.read().split('\n')
    path_roms = path_roms or './'
    assert os.path.isdir(path_roms)
    return os.listdir(path_roms)


def group_filelist(filelist, merge_data={}):
    """
    >>> import json
    >>> json.dumps(group_filelist(
    ...     filelist=(
    ...         'Rom Name 1 - Example [E].zip',
    ...         'Rom Name 1 - Example [U] [!].zip',
    ...         'Rom Name 1 - Example [U] [T-Hack].zip',
    ...         'Unrelated Name.zip',
    ...     ),
    ... ), cls=SetEncoder)
    '{"Rom Name 1 - Example": ["Rom Name 1 - Example [E].zip", "Rom Name 1 - Example [U] [!].zip", "Rom Name 1 - Example [U] [T-Hack].zip"], "Unrelated Name": ["Unrelated Name.zip"]}'

    >>> json.dumps(group_filelist(
    ...     filelist=(
    ...         'Rom Name 2 - More Example Better [E].zip',
    ...         'Rom Name 2 - More Example [U] [!].zip',
    ...         'Rom Name J - Japanese name [J].zip',
    ...         'Unrelated Name.zip',
    ...     ),
    ...     merge_data=parse_xmdb_dom(_load_xml('''<?xml version="1.0"?><!DOCTYPE romsets SYSTEM "GoodMerge.dtd">
    ...         <zoned>
    ...             <bias zone="En" name="Rom Name 2 - More Example"/>
    ...             <bias zone="J" name="Rom Name J - Japanese name"/>
    ...             <group reg="^Rom Name 2"/>
    ...         </zoned>
    ...     '''))
    ... ), cls=SetEncoder)
    '{"Rom Name 2 - More Example": ["Rom Name 2 - More Example Better [E].zip", "Rom Name 2 - More Example [U] [!].zip", "Rom Name J - Japanese name [J].zip"], "Unrelated Name": ["Unrelated Name.zip"]}'

    """
    log.info('merge')
    log.info(f'{len(filelist)} in filelist')

    def _normalize_filename(filename):
        normalized_filename = re.match(r'[^([]+', filename).group(0).strip()
        normalized_filename = re.sub(r'.zip$', '', normalized_filename)  # Remove extensions  TODO: added exts from xml
        normalized_filename = normalized_filename.lower().title()
        return normalized_filename

    def group_filelist(acc, filename):
        if not filename:
            return acc
        acc[_normalize_filename(filename)].add(filename)
        return acc
    grouped_filelist = reduce(group_filelist, filelist, defaultdict(set))

    # Parse 'Zones' - These associate esoteric names with the primary set
    def parse_zone(acc, zone_data):
        parent_name, data = zone_data
        parent_name = _normalize_filename(parent_name)

        # Identify groups
        to_merge = set()
        to_merge |= data['clones']
        to_merge |= {
            name
            for name in acc.keys()
            for regex in data['regex']
            if re.match(regex, name, flags=re.IGNORECASE)
        }
        to_merge = {_normalize_filename(name) for name in to_merge}
        to_merge -= {parent_name, }

        # Merge nodes into parent and remove
        for name in to_merge:
            if name not in acc:
                continue
            acc[parent_name] |= acc[name]
            del acc[name]

        return acc

    return reduce(parse_zone, merge_data.get('zoned', {}).items(), grouped_filelist)


class CompressionHelperTempfolder():
    """
    """
    def __init__(self, source_folder=None, destination_folder=None, working_folder=None, cmd_compress='', cmd_decompress='', cmd=subprocess.call, remove=os.remove, move=shutil.move, listdir=os.listdir, **kwargs):
        assert os.path.isdir(source_folder)
        self.source_folder = os.path.abspath(source_folder)

        self.cmd_decompress = tuple(cmd_decompress.split(' '))
        self.cmd_compress = tuple(cmd_compress.split(' '))
        self.cmd = cmd
        self.move = move
        self.remove = remove
        self.listdir = listdir

        self.destination_folder = os.path.abspath(destination_folder or source_folder)
        self.working_folder = os.path.abspath(working_folder) if working_folder else None
        self.temp_folder = None

    def __enter__(self):
        if not self.working_folder:
            self.temp_folder_object = TemporaryDirectory()
            self.temp_folder = self.temp_folder_object.name
            self.working_folder = self.temp_folder
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.temp_folder:
            self.temp_folder_object.cleanup()
            self.working_folder = None

    def prepare(self, source_filename):
        source_filename = os.path.join(self.source_folder, source_filename)
        if source_filename.endswith('.zip'):
            self.cmd(self.cmd_decompress + (source_filename, ) + (self.working_folder, ))
            self.remove(source_filename)
        else:
            self.move(source_filename, self.working_folder)

    def compress(self, destination_filename):
        destination_filename = os.path.abspath(os.path.join(self.destination_folder, destination_filename))
        working_filenames = tuple(map(partial(os.path.join, self.working_folder), self.listdir(self.working_folder)))
        self.cmd(self.cmd_compress + (destination_filename, ) + working_filenames)
        for filename in working_filenames:
            self.remove(filename)


def merge(grouped_filelist, compressor):
    for destination_filename, source_filenames in grouped_filelist.items():
        for source_filename in source_filenames:
            compressor.prepare(source_filename)
        compressor.compress(destination_filename)


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
    grouped_filelist = group_filelist(
        filelist=get_filelist(path_roms=kwargs.get('source_folder'), path_filelist=kwargs.get('path_filelist')),
        merge_data=parse_xmdb_dom(_load_xml(
            os.path.join(kwargs['path_xmdb'], TEMPLATE_FILENAME_XMDB.format(kwargs['type']))
        )),
    )
    with CompressionHelperTempfolder(**kwargs) as compressor:
        merge(grouped_filelist, compressor)


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
