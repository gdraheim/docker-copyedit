F= docker_copyedit/docker_copyedit.py
D=$(notdir $(F:.py=))

BASEYEAR= 2024
FOR=today

FILES = docker_copyedit/*.py *.toml
PYTHON3 = python3
PYTHON39 = $(PYTHON3)
MYPY = mypy
TWINE = twine
GIT = git
PARALLEL = -j2

ifeq ("$(wildcard /usr/bin/python3.9)","/usr/bin/python3.9")
  PYTHON39=python3.9
  TWINE=twine-3.9
  MYPY=mypy-3.9
endif

ifeq ("$(wildcard /usr/bin/python3.10)","/usr/bin/python3.10")
  PYTHON39=python3.10
  TWINE=twine-3.10
  MYPY=mypy-3.10
endif

ifeq ("$(wildcard /usr/bin/python3.11)","/usr/bin/python3.11")
  PYTHON39=python3.11
  TWINE=twine-3.11
  MYPY=mypy-3.11
endif

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
	@ ver=`sed -e '/^version *=/!d' -e 's/version *= *"//' -e 's/".*//'  pyproject.toml` \
	; echo ": $(GIT) commit -m $$ver"
tag:
	@ ver=`sed -e '/^version *=/!d' -e 's/version *= *"//' -e 's/".*//'  pyproject.toml` \
	; rev=`${GIT} rev-parse --short HEAD` \
	; if test -r tmp.changes.txt \
	; then echo ": ${GIT} tag -F tmp.changes.txt $$ver $$rev" \
	; else echo ": ${GIT} tag $$ver $$rev" ; fi

help:
	$(PYTHON3) docker_copyedit/docker_copyedit.py --help

###################################### TESTS
CENTOS=almalinux:9.5-20250307
UBUNTU=ubuntu:latest
check: ; $(MAKE) check3
# check2: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py -vv --python=python2 --image=$(CENTOS) --podman=no-podman
check2: ; $(MAKE) tmp/docker-copyedit.py \
	; cd tmp && ../docker_copyedit/docker_copyedit_tests.py -vv --python=python2 --image=$(CENTOS) --podman=no-podman --script=docker-copyedit.py
check3: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py -vv --python=python3 --image=$(CENTOS) --podman=podman
check4: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py -vv --python=python3 --image=$(CENTOS) --docker=podman
check5: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py -vv --python=python3 --image=$(CENTOS) --docker=podman --force

test_%: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py $@ -vv --python=python3 --image=$(CENTOS) --failfast --podman=podman
est_%: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py t$@ -vv --python=python3 --image=$(CENTOS) --failfast --podman=no-podman
t_%: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py tes$@ -vv --python=python3 --image=$(CENTOS) --docker=podman --force

centos/test_%: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py $(notdir $@) -vv --python=python3 --image=$(CENTOS) --podman=podman
ubuntu/test_%: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py $(notdir $@) -vv --python=python3 --image=$(UBUNTU) --podman=podman
centos: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py -vv --python=python3 --image=$(CENTOS) --podman=podman
ubuntu: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py -vv --python=python3 --image=$(UBUNTU) --podman=podman
tests:  ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py -vv --python=python3 --image=$(UBUNTU) --podman=podman \
            --xmlresults=../TEST-python3-ubuntu.xml

coverage: ; cd docker_copyedit && $(PYTHON3) docker_copyedit_tests.py -vv --python=python3 --image=$(CENTOS) --podman=podman \
            --xmlresults=../TEST-python3-centos.xml --coverage

clean:
	- rm *.pyc 
	- rm -rf *.tmp
	- rm -rf tmp tmp.files
	- rm TEST-*.xml
	- rm -rf .coverage *,cover tmp.coverage.xml
	$(MAKE) distclean

############## https://pypi.org/project/docker-copyedit/

README: README.md Makefile
	cat README.md | sed -e "/\\/badge/d" -e /take.patches/d -e /however.please/d > README

.PHONY: build
build:
	$(MAKE) distclean
	$(MAKE) $(PARALLEL) README tmp/docker-copyedit.py
	# pip install --root=~/local . -v
	$(PYTHON39) -m build
	- rm README
	- rm -r tmp
	$(MAKE) fix-metadata-version
	$(TWINE) check dist/*
	: $(TWINE) upload dist/*

distclean:
	- rm -rf build dist *.egg-info README

fix-metadata-version:
	ls dist/*
	rm -rf dist.tmp; mkdir dist.tmp
	cd dist.tmp; for z in ../dist/*; do case "$$z" in *.whl) unzip $$z ;; *) tar xzvf $$z;; esac \
	; ( find . -name PKG-INFO ; find . -name METADATA ) | while read f; do echo FOUND $$f; sed -i -e "s/Metadata-Version: 2.4/Metadata-Version: 2.2/" $$f; done \
	; case "$$z" in *.whl) zip -r $$z * ;; *) tar czvf $$z *;; esac ; ls -l $$z; done

# ------------------------------------------------------------
PIP3=$(PYTHON39) -m pip
install:
	$(MAKE) distclean
	$(MAKE) $(PARALLEL) README tmp/docker-copyedit.py
	$(PIP3) install .
	$(MAKE) showfiles | grep -v dist-info
uninstall:
	test -d tmp || mkdir -v tmp
	cd tmp && $(PIP3) uninstall -y `sed -e '/^name *=/!d' -e 's/name *= *"//' -e 's/".*//'  ../pyproject.toml`
showfiles:
	@ test -d tmp || mkdir -v tmp
	@ cd tmp && $(PIP3) show --files `sed -e '/^name *=/!d' -e 's/name *= *"//' -e 's/".*//'  ../pyproject.toml` \
	| sed -e "s:[^ ]*/[.][.]/\\([a-z][a-z]*\\)/:~/.local/\\1/:"
show:
	test -d tmp || mkdir -v tmp
	cd tmp && $(PIP3) show -f $$(sed -e '/^name *=/!d' -e 's/name *= *"//' -e 's/".*//'  ../pyproject.toml)

# ------------------------------------------------------------

.PHONY: docker-test docker-example docker
docker-test: docker-example
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock $D:tests -vv
docker-example: docker
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock $D:latest FROM $D:latest INTO $D:tests set entrypoint $(D)_tests.py
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

tmp/docker-copyedit.py: docker_copyedit/docker_copyedit.py $(STRIP_PYTHON3)
	@ test -d $(dir $@) || mkdir -v $(dir $@)
	@ $(STRIPHINTS3) $< -o $@ -y $V --remove-comments --run-python=$(notdir $(PYTHON3))

mypy:
	zypper install -y mypy
	zypper install -y python3-click python3-pathspec

# mypy 1.0.0 has minimum --python-version 3.7
# mypy 1.9.0 has minimum --python-version 3.8
# MYPY = mypy
MYPY_STRICT = --strict --show-error-codes --show-error-context --no-warn-unused-ignores --python-version 3.8
PYLINT = pylint
PYLINT_OPTIONS =

%.type:
	$(MYPY) $(MYPY_STRICT) $(MYPY_OPTIONS) $(@:.type=)
	- rm -rf .mypy_cache
%.lint:
	$(PYLINT) $(PYLINT_OPTIONS) $(@:.lint=)

type: \
    docker_copyedit/docker_copyedit.py.type docker_copyedit/docker_copyedit_tests.py.type
style lint: \
    docker_copyedit/docker_copyedit.py.lint  docker_copyedit/docker_copyedit_tests.py.lint
