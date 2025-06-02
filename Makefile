F= docker-copyedit.py
D=$(basename $F)

BASEYEAR= 2024
FOR=today

FILES = *.py *.cfg
PYTHON3 = python3
GIT = git
PARALLEL = -j2

version1:
	@ grep -l __version__ $(FILES) | { while read f; do echo $$f; done; } 

version:
	@ grep -l __version__ $(FILES) | { while read f; do : \
	; THISYEAR=`date +%Y -d "$(FOR)"` ; Y=$$(expr $$THISYEAR - $(BASEYEAR)) \
	; WWD=`date +%W%u -d "$(FOR)"` ; sed -i \
	-e "/^version /s/[.]-*[0123456789][0123456789][0123456789]*/.$$Y$$WWD/" \
	-e "/^ *__version__/s/[.]-*[0123456789][0123456789][0123456789]*\"/.$$Y$$WWD\"/" \
	-e "/^ *__version__/s/[.]\\([0123456789]\\)\"/.\\1.$$Y$$WWD\"/" \
	-e "/^ *__copyright__/s/(C) \\([0123456789]*\\)-[0123456789]*/(C) \\1-$$THISYEAR/" \
	-e "/^ *__copyright__/s/(C) [0123456789]* /(C) $$THISYEAR /" \
	$$f; done; }
	@ grep ^__version__ $(FILES)
	@ $(MAKE) commit
commit:
	@ ver=`grep "version.*=" setup.cfg | sed -e "s/version *= */v/"` \
	; echo ": $(GIT) commit -m $$ver"
tag:
	@ ver=`grep "version.*=" setup.cfg | sed -e "s/version *= */v/"` \
	; rev=`${GIT} rev-parse --short HEAD` \
	; if test -r tmp.changes.txt \
	; then echo ": ${GIT} tag -F tmp.changes.txt $$ver $$rev" \
	; else echo ": ${GIT} tag $$ver $$rev" ; fi

help:
	python docker-copyedit.py --help

###################################### TESTS
CENTOS=centos:centos8
UBUNTU=ubuntu:latest
check: ; $(MAKE) check0 && $(MAKE) check3
check0: ; test ! -f ../retype/retype.py || $(MAKE) type
check2: ; ./docker-copyedit-tests.py -vv --python=python2 --image=$(CENTOS) --podman=no-podman
check3: ; ./docker-copyedit-tests.py -vv --python=python3 --image=$(CENTOS) --podman=podman
check4: ; ./docker-copyedit-tests.py -vv --python=python3 --image=$(CENTOS) --docker=podman
check5: ; ./docker-copyedit-tests.py -vv --python=python3 --image=$(CENTOS) --docker=podman --force

test_%: ; ./docker-copyedit-tests.py $@ -vv --python=python3 --image=$(CENTOS) --failfast --podman=podman
est_%: ; ./docker-copyedit-tests.py t$@ -vv --python=python2 --image=$(CENTOS) --failfast --podman=no-podman
t_%: ; ./docker-copyedit-tests.py tes$@ -vv --python=python3 --image=$(CENTOS) --docker=podman --force

centos/test_%: ; ./docker-copyedit-tests.py $(notdir $@) -vv --python=python3 --image=$(CENTOS) --podman=podman
ubuntu/test_%: ; ./docker-copyedit-tests.py $(notdir $@) -vv --python=python3 --image=$(UBUNTU) --podman=podman
centos: ; ./docker-copyedit-tests.py -vv --python=python3 --image=$(CENTOS) --podman=podman
ubuntu: ; ./docker-copyedit-tests.py -vv --python=python3 --image=$(UBUNTU) --podman=podman
tests:  ; ./docker-copyedit-tests.py -vv --python=python3 --image=$(UBUNTU) --podman=podman \
            --xmlresults=TEST-python3-ubuntu.xml

coverage: ; ./docker-copyedit-tests.py -vv --python=python3 --image=$(CENTOS) --podman=podman \
            --xmlresults=TEST-python3-centos.xml --coverage

clean:
	- rm *.pyc 
	- rm -rf *.tmp
	- rm -rf tmp tmp.files
	- rm TEST-*.xml
	- rm -rf .coverage *,cover tmp.coverage.xml
	- rm setup.py README
	- rm -rf build dist *.egg-info

############## https://pypi.org/project/docker-copyedit/

README: README.md Makefile
	cat README.md | sed -e "/\\/badge/d" -e /take.patches/d -e /however.please/d > README
setup.py: Makefile
	{ echo '#!/usr/bin/env python3' \
	; echo 'import setuptools' \
	; echo 'setuptools.setup()' ; } > setup.py
	chmod +x setup.py
setup.py.tmp: Makefile
	echo "import setuptools ; setuptools.setup()" > setup.py

sdist bdist bdist_wheel:
	- rm -rf build dist *.egg-info
	$(MAKE) $(PARALLEL) README setup.py tmp/docker-copyedit.py
	$(PYTHON3) setup.py $@
	- rm setup.py README

.PHONY: build
build:
	- rm -rf build dist *.egg-info
	$(MAKE) $(PARALLEL) README setup.py tmp/docker-copyedit.py
	# pip install --root=~/local . -v
	$(PYTHON3) setup.py sdist
	- rm setup.py README
	twine check dist/*
	: twine upload dist/*
# ------------------------------------------------------------
PIP3=$(PYTHON3) -m pip
install:
	$(MAKE) setup.py
	$(MAKE) tmp/docker-copyedit.py
	trap "rm -v setup.py" SIGINT SIGTERM ERR EXIT ; \
	$(PIP3) install .
	$(MAKE) showfiles | grep /.local/
uninstall:
	test -d tmp || mkdir -v tmp
	cd tmp && $(PIP3) uninstall -y `sed -e '/^name *=/!d' -e 's/.*= *//' ../setup.cfg`
showfiles:
	@ test -d tmp || mkdir -v tmp
	@ cd tmp && $(PIP3) show --files `sed -e '/^name *=/!d' -e 's/.*= *//' ../setup.cfg` \
	| sed -e "s:[^ ]*/[.][.]/\\([a-z][a-z]*\\)/:~/.local/\\1/:"
show:
	test -d tmp || mkdir -v tmp
	cd tmp && $(PIP3) show -f $$(sed -e '/^name *=/!d' -e 's/.*= *//' ../setup.cfg)

# ------------------------------------------------------------

.PHONY: docker-test docker-example docker
docker-test: docker-example
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock $D:tests -vv
docker-example: docker
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock $D:latest FROM $D:latest INTO $D:tests set entrypoint $D-tests.py
docker:
	docker build . -t $D:latest

####### types
STRIP_PYTHON3_GIT_URL = https://github.com/gdraheim/strip_python3
STRIP_PYTHON3_GIT = ../strip_python3
STRIP_PYTHON3 = $(STRIP_PYTHON3_GIT)/strip3/strip_python3.py
STRIPHINTS3 = $(PYTHON39) $(STRIP_PYTHON3) $(STRIP_PYTHON3_OPTIONS)
striphints3.git:
	set -ex ; if test -d $(STRIP_PYTHON3_GIT); then cd $(STRIP_PYTHON3_GIT) && git pull; else : \
	; cd $(dir $(STRIPHINTS_GIT)) && git clone $(STRIP_PYTHON3_GIT_URL) $(notdir $(STRIP_PYTHON3_GIT)) \
	; fi
	echo "def test(a: str) -> str: return a" > tmp.striphints.py
	$(STRIPHINTS3) tmp.striphints.py -o tmp.striphints.py.out -vv
	cat tmp.striphints.py.out | tr '\\\n' '|' && echo
	test "def test(a):|    return a|" = "`cat tmp.striphints.py.out | tr '\\\\\\n' '|'`"
	rm tmp.striphints.*

tmp/docker-copyedit.py: docker-copyedit.py $(STRIP_PYTHON3)
	@ test -d $(dir $@) || mkdir -v $(dir $@)
	@ $(STRIPHINTS3) $< -o $@ -y $V --remove-comments --run-python=$(notdir $(PYTHON3))

mypy:
	zypper install -y mypy
	zypper install -y python3-click python3-pathspec

# mypy 1.0.0 has minimum --python-version 3.7
# mypy 1.9.0 has minimum --python-version 3.8
MYPY = mypy
MYPY_STRICT = --strict --show-error-codes --show-error-context --no-warn-unused-ignores --python-version 3.8
AUTOPEP8=autopep8
AUTOPEP8_INPLACE= --in-place

%.type:
	$(MYPY) $(MYPY_STRICT) $(MYPY_OPTIONS) $(@:.type=)
	- rm -rf .mypy_cache
%.pep8:
	$(AUTOPEP8) $(AUTOPEP8_INPLACE) $(AUTOPEP8_OPTIONS) $(@:.pep8=)
	${GIT} --no-pager diff $(@:.pep8=)

type: \
    docker-copyedit.py.type docker-copyedit-tests.py.type
style pep: \
    docker-copyedit.py.pep8  docker-copyedit-tests.py.pep8 \
    docker-copyedit.pyi.pep8
