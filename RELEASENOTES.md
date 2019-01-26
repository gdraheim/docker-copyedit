The release 1.2 is based on changes to the parser.
It has moved the ALL flag from the edit_image executor
to the parsing routine where it will be replaced by a
star `*` argument to REMOVE VOLUMES and REMOVE PORTS.

With a more widespread usage a couple of small bugs
did come up. This includes lowercase/uppercase handling
in the parser. And the point that a missing ':version'
must be put as ':latest' into the output tarball to be
loaded correctly.

There are more problems with people to expect to be 
able to use any image name where in fact the docker
tagging format is quite restricted. The tool will now
warn on a lot of common problems as far as they are
documented in the docker documentation.
