help:
	#

config.json:
	cp config.dist.json $@

install: config.json

var/xmdb:
	mkdir -p $*
	curl https://downloads.sourceforge.net/project/goodmerge/GoodMerge%20XMDBs/XMDBs%20%28Goodtools%20v0.xx%20-%20v3.14%29.zip?r=https%3A%2F%2Fsourceforge.net%2Fprojects%2Fgoodmerge%2Ffiles%2F
	unzip

run:
	python3 goodMerge.py --postmortem --log_level 0 --path_filelist ./var/rom_lists/gba.txt --xmdb_type gba --postmortem

test:
	pytest --pdb --doctest-modules
