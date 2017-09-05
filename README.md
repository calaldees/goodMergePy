goodMergePy
===========

[GoodMerge](http://goodmerge.sourceforge.net/About.php) is a windows based tool for grouping Good{Sets} as [7zip](http://www.7-zip.org/) solid archives to dramatically improve organization and compression of romsets.

`goodMergePy` is a cross platform [Python](https://www.python.org/) re-implementation of a subset of `GoodMerge`'s behavior.


What `GoodMerge` does
---------------------

GoodMerge does two core roles.

1. Groups roms automatically by `filename` e.g.

    ```
        # Input
        Rom Name 1 - Example [U] [!].zip
        Rom Name 1 - Example [U] [T-Hack].zip
        Rom Name 1 - Example [E].zip
        Unrelated Name.zip
    ```

   Is grouped as

    ```
        # Output
        Rom Name 1 - Example.7z
            Rom Name 1 - Example [U] [!]
            Rom Name 1 - Example [U] [T-Hack]
            Rom Name 1 - Example [E]
        Unrelated Name.7z
            Unrelated Name
    ```

2. Groups roms from additional `xmdb` (xml) file. Downloadable form the [GoodMerge](http://goodmerge.sourceforge.net/Download.php) site.

    ```
        # Input
        Rom Name 2 - More Example [U] [!].zip
        Rom Name 2 - More Example Better [E].zip
        Rom Name J - Japanese name [J].zip
        Unrealted Name.zip
    ```

    ```xml
        <zoned>
            <bias zone="En" name="Rom Name 2 - More Example"/>
            <bias zone="J" name="Rom Name J - Japanese name"/>
            <group reg="^Rom Name 2"/>
        </zoned>
    ```

    ```
        # Output
        Rom Name 2 - More Example.7z
            Rom Name 2 - More Example [U] [!]
            Rom Name 2 - More Example Better [E]
            Rom Name J - Japanese name [J]
        Unrealted Name.7z
            Unrealted Name
    ```

Setup
-----

### Dependencies

* Python 3.6+
* `7za` command-line tool available


Use
---

    # TODO


Appendix
-------

Often this tool is used in conjunction with a range of other operations.
Below is a reference of `bash` commands that are useful for further management of Good{Sets}.

    # Remove all video `[v]` roms

    # GoodUnMerge
    #   Reverse the `goodMergePy` process


Dev Notes (to be removed)
-------------------------

    python3 goodMerge.py --postmortem --log_level 0 --path_filelist ./var/rom_lists/gba.txt gba

    from pprint import pprint ; pprint({k:v for k,v in data.items() if k.startswith('Metroid')})
    from pprint import pprint ; pprint({k:len(v) for k, v in data.items() if k.startswith('m')})

    re.sub(r'[^\w]', '', """helo dudes2 it's showtime""")
