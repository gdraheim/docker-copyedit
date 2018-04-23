F= docker-copyedit.py
B= 2017

FILES = *.py

version1:
	@ grep -l __version__ $(FILES) | { while read f; do echo $$f; done; } 

version:
	@ grep -l __version__ $(FILES) | { while read f; do : \
	; Y=`date +%Y` ; X=$$(expr $$Y - $B); D=`date +%W%u` ; sed -i \
	-e "/^ *__version__/s/[.]-*[0123456789][0123456789][0123456789]*\"/.$$X$$D\"/" \
	-e "/^ *__version__/s/[.]\\([0123456789]\\)\"/.\\1.$$X$$D\"/" \
	-e "/^ *__copyright__/s/(C) [0123456789]*-[0123456789]*/(C) $B-$$Y/" \
	-e "/^ *__copyright__/s/(C) [0123456789]* /(C) $$Y /" \
	$$f; done; }
	@ grep ^__version__ $(FILES)

help:
	python docker-copyedit.py --help

test_%: ; ./docker-copyedit-tests.py $@ -vv

check: ; ./docker-copyedit-tests.py -vv

clean:
	- rm *.pyc 
	- rm -rf *.tmp

