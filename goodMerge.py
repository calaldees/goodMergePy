#!/usr/local/bin/python3

import os
import re
import json
import xml.dom.minidom
from functools import reduce
from collections import defaultdict
from tempfile import TemporaryDirectory
import shutil
from functools import partial
from itertools import chain
import subprocess
import logging
import operator

log = logging.getLogger(__name__)


def os_path_normalize(*args, **kwargs):
    return os.path.abspath(os.path.expanduser(*args, **kwargs), **kwargs)

# Constants --------------------------------------------------------------------
VERSION = 'v0.0.0'
DESCRIPTION = """
`goodMergePy` is a cross platform [Python](https://www.python.org/) re-implementation of a subset of [GoodMerge](http://goodmerge.sourceforge.net/About.php)'s behavior.
An external compression tool (such as `7z`) is required.
"""
DEFAULT_CONFIG_FILENAME = 'config.json'
DEFAULT_REGEX_FLAG = re.compile(r'(\(.+?\)|\[.+?\])')


def endswith_oneof(s, exts=set()):
    """
    >>> exts = {'zip', '7z', 'e+'}
    >>> endswith_oneof('.bin', exts)
    False
    >>> endswith_oneof('bob.zip', exts)
    True
    >>> endswith_oneof('Another Test.e+', exts)
    True
    """
    return any(s.endswith(ext) for ext in exts)


# TODO: these could be moved to config.json values rather than constants
COMPRESSED_EXTENSIONS = {'zip', '7z', 'gzip', 'tar'}


# Utils ------------------------------------------------------------------------

def _listdir(path='./'):
    assert os.path.isdir(path)
    return os.listdir(path)


def _listfile(path):
    assert os.path.isfile(path)
    with open(path, 'rt') as filehandle:
        return filehandle.read().split('\n')


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
    def _parse_zone(acc, node):
        #deferred = bool(node.getAttribute('deferred'))
        childNodeElements = tuple(filter(lambda node: node.nodeType == node.ELEMENT_NODE, node.childNodes))
        if not childNodeElements:
            return acc
        if node.tagName == 'parent':
            parent_name = node.getAttribute('name')
        elif node.tagName == 'zoned':
            parent_name = childNodeElements[0].getAttribute('name')
            childNodeElements = childNodeElements[1:]
        else:
            log.debug(f'Unsupported element {node.tagName}')
            return acc
        def _group_nodes(acc, node):
            if node.nodeType == node.ELEMENT_NODE:
                if node.tagName in ('bias', 'clone') and node.getAttribute('name'):
                    acc['clones'].add(node.getAttribute('name'))
                if node.tagName in ('group'):
                    #regex_type = 'regex' if node.getAttribute('type') != 'filename' else 'regex_filename'
                    if node.getAttribute('reg'):
                        acc['regex'].add(node.getAttribute('reg'))
                    if node.getAttribute('regf'):
                        acc['regexf'].add(node.getAttribute('regf'))
            return acc
        acc[parent_name] = reduce(_group_nodes, childNodeElements, {
            'regex': set(), 'clones': set(), 'regexf': set(),
        })
        return acc

    def _parse_ext(acc, node):
        acc.add(node.getAttribute('text'))
        return acc

    def get_flag(dom):
        for flag_node in dom.getElementsByTagName('flag'):
            return flag_node.getAttribute('reg')

    return {
        'zoned': reduce(_parse_zone, dom.getElementsByTagName('zoned'), {}),
        'parent': reduce(_parse_zone, dom.getElementsByTagName('parent'), {}),
        'ext': reduce(_parse_ext, dom.getElementsByTagName('ext'), set()),
        'flag': get_flag(dom),
    }


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
    ...         <romsets><set name="Test" version="0.00">
    ...             <parent name="Rom Name 2">
    ...                 <group reg="^Rom Name 2"/>
    ...             </parent>
    ...             <zoned>
    ...                 <bias zone="En" name="Rom Name 2 - More Example"/>
    ...                 <clone zone="J" name="Rom Name J - Japanese name"/>
    ...             </zoned>
    ...         </set></romsets>
    ...     '''))
    ... ), cls=SetEncoder)
    '{"Unrelated Name": ["Unrelated Name.zip"], "Rom Name 2": ["Rom Name 2 - More Example Better [E].zip", "Rom Name 2 - More Example [U] [!].zip", "Rom Name J - Japanese name [J].zip"]}'

    TODO: The above test is flaky and implementation dependent. We should sort the key order alphabetically
    """
    REGEX_FLAG = re.compile(merge_data.get('flag')) if merge_data.get('flag') else DEFAULT_REGEX_FLAG

    def _normalize_filename(filename):
        flags = set(match.group(0) for match in REGEX_FLAG.finditer(filename))
        normalized_filename = reduce(lambda filename, flag: filename.replace(flag, ''), flags, filename)
        #normalized_filename = re.match(r'[^([]+', filename).group(0).strip()
        normalized_filename = re.sub(r'\..{1,4}$', '', normalized_filename)  # Remove extensions  TODO: added exts from xml
        normalized_filename = re.sub(r' +', r' ', normalized_filename.strip().lower().title())
        return normalized_filename

    def group_by_filename(acc, filename):
        if not filename:
            return acc
        acc[_normalize_filename(filename)].add(filename)
        return acc
    grouped_filelist = reduce(group_by_filename, filelist, defaultdict(set))

    # Parse 'Zones' - These associate esoteric names with the primary set
    def parse_group_node(acc, parent_name_pairedwith_xmdb):
        parent_name, xmdb_data = parent_name_pairedwith_xmdb
        parent_name = _normalize_filename(parent_name)
        acc[parent_name]  # Create entry in filelist (some alias names wont be present yet) [acc is a defaultdict]

        #def is_regex_trying_to_match_flags(regex):
        #    return r'\(' in regex or r'\)' in regex
        #regexs_on_filenames = tuple(filter(is_regex_trying_to_match_flags, xmdb_data['regex']))
        regexs_on_keys = xmdb_data.get('regex') or ()
        regexs_on_filenames = xmdb_data.get('regexf') or ()

        # Identify groups
        to_merge = set()
        to_merge |= xmdb_data['clones']
        to_merge |= {
            name
            for name in acc.keys()
            for regex in regexs_on_keys
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

        # HACK: Special case filenames. I'm so so sorry ...
        for regex in regexs_on_filenames:
            for key, filenames in acc.items():
                filenames_to_steal = {filename for filename in filenames if re.search(regex, filename, flags=re.IGNORECASE)}
                acc[parent_name] |= filenames_to_steal
                if key != parent_name:
                    filenames -= filenames_to_steal

        return acc

    return reduce(parse_group_node, chain(
        merge_data.get('zoned', {}).items(),
        merge_data.get('parent', {}).items(),
    ), grouped_filelist)


class CompressionHelperTempfolder():
    """
    """
    def __init__(self, source_folder=None, destination_folder=None, working_folder=None, cmd_compress="""7z a {destination_file}""", cmd_decompress="""7z e -o{destination_folder}""", cmd_call=subprocess.call, cmd_remove=os.remove, cmd_move=shutil.move, cmd_listdir=os.listdir, compressed_extension='7z', **kwargs):
        assert source_folder
        self.source_folder = os_path_normalize(source_folder)
        assert os.path.isdir(self.source_folder)
        self.destination_folder = os_path_normalize(destination_folder or source_folder)
        assert os.path.isdir(self.destination_folder)
        self.working_folder = os_path_normalize(working_folder) if working_folder else None
        self.compressed_extension = compressed_extension

        def _cmd_call_string(cmd_string, *args, **kwargs):
            return cmd_call(tuple(cmd_string.format(**kwargs).split(' ')) + args)

        self.cmd = {
            'compress': partial(_cmd_call_string, cmd_compress),
            'decompress': partial(_cmd_call_string, cmd_decompress),
            'move': cmd_move,
            'remove': cmd_remove,
            'listdir': lambda folder: tuple(map(partial(os.path.join, folder), cmd_listdir(folder))),
        }

        self.temp_folder_object = None

    def __enter__(self):
        if not self.working_folder:
            self.temp_folder_object = TemporaryDirectory()
            self.working_folder = self.temp_folder_object.name
        assert self.working_folder and os.path.isdir(self.working_folder)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.temp_folder_object:
            self.temp_folder_object.cleanup()
            self.working_folder = None

    def prepare(self, source_filename):
        def current_working_files_count():
            return len(self.cmd['listdir'](self.working_folder))
        starting_working_file_count = current_working_files_count()
        source_filename = os.path.join(self.source_folder, source_filename)
        assert os.path.exists(source_filename)
        if endswith_oneof(source_filename, COMPRESSED_EXTENSIONS):
            self.cmd['decompress'](source_filename, destination_folder=self.working_folder)
        else:
            self.cmd['move'](source_filename, self.working_folder)
        assert starting_working_file_count < current_working_files_count()
        if os.path.exists(source_filename):
            self.cmd['remove'](source_filename)
        assert not os.path.exists(source_filename)

    def compress(self, destination_filename):
        destination_filename = os.path.join(self.destination_folder, f'{destination_filename}.{self.compressed_extension}')
        working_filenames = self.cmd['listdir'](self.working_folder)
        assert not os.path.isfile(destination_filename)
        self.cmd['compress'](*working_filenames, destination_file=destination_filename)
        assert os.path.isfile(destination_filename)
        for filename in working_filenames:
            self.cmd['remove'](filename)
            assert not os.path.exists(filename)


def merge(grouped_filelist, compressor):
    for destination_filename, source_filenames in grouped_filelist.items():
        for source_filename in source_filenames:
            compressor.prepare(source_filename)
        log.info(destination_filename)
        compressor.compress(destination_filename)


# Command Line Arguments -------------------------------------------------------

def get_args():
    import argparse

    parser = argparse.ArgumentParser(
        prog=__name__,
        description=DESCRIPTION,
    )

    parser.add_argument('--source_folder', action='store', help='path for input roms')
    parser.add_argument('--destination_folder', action='store', help='optional: If ommited source_folder is used')
    parser.add_argument('--path_xmdb', action='store', help='')
    parser.add_argument('--xmdb_filename_template', action='store', help='required if using xmdb_type')
    parser.add_argument('--xmdb_type', action='store', help='romset shorthand name. e.g. snes, gba, sms')

    parser.add_argument('--cmd_decompress', action='store', help='templated commandline to decompress. See config.dist.json for examples')
    parser.add_argument('--cmd_compress', action='store', help='templated commandline to compress. See config.dist.json for examples')

    parser.add_argument('--exclude_file_regex', action='store', help='regex to exclude files from filelist')

    parser.add_argument('--config', action='store', help='json file with preset commandline paramiter values', default=DEFAULT_CONFIG_FILENAME)
    parser.add_argument('--path_filelist', action='store', help='read filelist from file for debugging. Used in place of source_folder')
    parser.add_argument('--dryrun', action='store_true', help='dont compress files and output json')
    parser.add_argument('--postmortem', action='store_true', help='enter python debugger on error')
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
    if kwargs.get('path_filelist'):
        filelist = _listfile(kwargs.get('path_filelist'))
    else:
        filelist = _listdir(kwargs.get('source_folder'))
    assert filelist

    # Load group data
    xmdb_data = {}
    if kwargs.get('path_xmdb'):
        xmdb_path = os_path_normalize(kwargs.get('path_xmdb'))
        xmdb_filename = ''
        if os.path.isfile(xmdb_path):
            xmdb_filename = xmdb_path
        elif kwargs.get('xmdb_filename_template') and kwargs.get('xmdb_type'):
            xmdb_filename = os.path.join(xmdb_path, kwargs['xmdb_filename_template'].format(kwargs['xmdb_type']))
        if os.path.isfile(xmdb_filename):
            log.info(f'Loading xmdb: {xmdb_filename}')
            xmdb_data = parse_xmdb_dom(_load_xml(xmdb_filename))
        else:
            raise Exception('Insufficient commandline variables provided to identify xmdb file.')

    # Filter filelist to known extensions
    filename_endswith_supported_extension = partial(endswith_oneof, exts=xmdb_data.get('ext', set()) | COMPRESSED_EXTENSIONS)
    filelist = tuple(filter(filename_endswith_supported_extension, filelist))

    # Grouping Logic
    grouped_filelist = group_filelist(filelist=filelist, merge_data=xmdb_data)

    # Exclude
    if kwargs.get('exclude_file_regex'):
        exclude_file_regex = re.compile(kwargs['exclude_file_regex'], flags=re.IGNORECASE)
        keys_to_remove = set()
        for key, filenames in grouped_filelist.items():
            filenames -= {filename for filename in filenames if exclude_file_regex.search(filename)}
            if not filenames or exclude_file_regex.search(key):
                keys_to_remove.add(key)
        for key in keys_to_remove:
            del grouped_filelist[key]

    log.info(f'filelist: {len(filelist)} grouped_filelist: {len(grouped_filelist.keys())}')

    if kwargs.get('source_folder') and not kwargs.get('dryrun'):
        # Merge & Compress
        with CompressionHelperTempfolder(**kwargs) as compressor:
            merge(grouped_filelist, compressor)
    else:
        # Output json
        print(json.dumps(grouped_filelist, cls=SetEncoder))


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
