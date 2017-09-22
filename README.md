goodMergePy
===========

[GoodMerge](http://goodmerge.sourceforge.net/About.php) is a windows based tool for grouping Good{Sets} as [7zip](http://www.7-zip.org/) solid archives to dramatically improve organization and compression of romsets.

`goodMergePy` is a cross platform [Python](https://www.python.org/) re-implementation of a subset of `GoodMerge`'s behavior.

The original `GoodMerge` has been abandoned since 2009.
There is a more modern fork [GoodMerge2](https://www.github.com/subtract1/GoodMerge2) with updated xmdb files.

* This project does not behave exactly like `GoodMerge`
* This project was created initially to sort and manage the `gba` romset. My `xmdb` is included.
* I didn't quite understand the subtleties of how the `xmdb` was used and guessed/hacked my way to glory. Advice/guidance with `xmdb` files would be appreciated.


What `GoodMerge` does
---------------------

GoodMerge does two core roles.

1. Groups roms automatically (with no xmdb) by `filename` e.g.

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

2. Groups roms from additional `xmdb` (xml) file. Downloadable form the [GoodMerge](http://goodmerge.sourceforge.net/Download.php) or [GoodMerge2](https://www.github.com/subtract1/GoodMerge2) site.

    ```
        # Input
        Rom Name 2 - More Example [U] [!].zip
        Rom Name 2 - More Example Better [E].zip
        Rom Name J - Japanese name [J].zip
        Unrealted Name.zip
    ```

    ```xml
    <?xml version="1.0"?><!DOCTYPE romsets SYSTEM "GoodMerge.dtd">
    <romsets><set name="Test" version="0.00">
        <parent name="Rom Name 2">
            <group reg="^Rom Name 2"/>
        </parent>
        <zoned>
            <bias zone="En" name="Rom Name 2 - More Example"/>
            <clone zone="J" name="Rom Name J - Japanese name"/>
        </zoned>
    </set></romsets>
    ```

    ```
        # Output
        Rom Name 2.7z
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

    goodMerge.py --help


Appendix
-------

Often this tool is used in conjunction with a range of other operations.
Below is a reference of `bash` commands that are useful for further management of Good{Sets}.

    # TODO
    # GoodUnMerge
    #   Reverse the `goodMergePy` process
