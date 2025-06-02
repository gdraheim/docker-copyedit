The release 1.5 is a switch from setup.cfg to pyproject.toml
alias PEP517 package build. Newer `pip` and `twine` will pick
that up.

And 1.5 has moved the main source from `docker-copyedit.py`
into `docker_copyedit/docker_copyedit.py` to allow for mypy
py.typed imports according to PEP561. The pyproject will
install a `bin/docker-copyedit` wrapper that you should use
in the future. `bin/docker-copyedit.py` is only left
for backward compatibility (depends on `gdraheim/strip-python3`).

The release 1.4 is a switch to Python3. So anyone
downloading the script directly from Github
may experience problems.

The docker-copyedit.py binary does support a few
new options. Using "-c KEEPOUTPUTFILE=y" one can
specifically keep that file instead of using -kkk.
The number of -kk has also changed as the default
has changed to skip the saved.tar generation.

Additionally it is possible to provide a path to
some --docker=/other/binary but tests with podman
have shown that it is incompatible (although the
bug reports show that it may be fixed in the next
version of podman).



