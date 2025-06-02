The release 1.4 is a switch to Python3. So anyone
downloading the script directly from Github
may experience problems.

The build system does also take advantage of type
checking the code with retype+mypy. Static code
analysis is simply better than just relying on 
a testsuite to cover everything.

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

The provided setup.cfg file allows to package a
bdist_wheel universal distribution.



