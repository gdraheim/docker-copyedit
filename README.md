[![Style Check](https://github.com/gdraheim/docker-copyedit/actions/workflows/stylecheck.yml/badge.svg?event=push)](https://github.com/gdraheim/docker-copyedit/actions/workflows/stylecheck.yml)
[![Type Check](https://github.com/gdraheim/docker-copyedit/actions/workflows/typecheck.yml/badge.svg?event=push)](https://github.com/gdraheim/docker-copyedit/actions/workflows/typecheck.yml)
[![Code Coverage](https://img.shields.io/badge/64%20test-75%25%20coverage-brightgreen)](https://github.com/gdraheim/docker-copyedit/blob/master/docker-copyedit-tests.py)
[![PyPI version](https://badge.fury.io/py/docker-copyedit.svg)](https://pypi.org/project/docker-copyedit/)
[![PyPI downloads](https://img.shields.io/pypi/dm/docker-copyedit)](https://pypi.org/project/docker-copyedit/#files)

# edit docker image metadata

The initial motiviation for the creation of the tool came from
the fact that it is not possible to remove VOLUME entries in
an image. You can basically change a USER or WORKDIR setting
but you can only ever add VOLUME and PORT entries.

The wish to REMOVE ALL VOLUMES came from the fact that I did
want to download a tested image for local tests where the
data part should be committed to the history as well in order
to turn back both program and data to a defined state so that 
another test run will start off the exact same checkpoint.

While docker does not allow to edit the metadata of an image
directly, there is a workaround - one may "docker save" an
image into an archive file that contains all the layers and
metadata json files. After modifying the content one can
"docker load" the result back with the history being preserved.

Correcting some images from other sources became such a
regular task that I started to fill in a python script to
help with the daily work. In order to allow coworkers to
understand what was intended, the input syntax is somewhat
descriptive (likeSQL).

     ./docker-copyedit.py \
     FROM image1 INTO image2 REMOVE ALL VOLUMES
         
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         add volume /var/tmp
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         REMOVE VOLUME /var/atlassian/jira-data
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         REMOVE VOLUMES '/var/*' AND RM PORTS 80%0
     
     ./docker-copyedit.py \
         into image2 from image1 set no user
     ./docker-copyedit.py \
         set null user and set null cmd from image1 into image2
     ./docker-copyedit.py FROM image1 INTO image2 \
         set null user + set null cmd + rm all volumes

     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         set null entrypoint and set cmd /entrypoint.sh
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         set shell cmd "/entrypoint.sh foo"
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         set label author "real me" and rm labels old%
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         set env MAINDIR "/path" and rm env backupdir

     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         REMOVE PORT 4444
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         remove port ldap and rm port ldaps
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         remove all ports
     ./docker-copyedit.py FROM image1 INTO image2 -vv \
         add port ldap and add port ldaps

Of course you may have image1 and image2 to be the same
tag name but remember that the image hash value will 
change while copyediting the image archive on the disk.
You will be left with a dangling old (untagged) image.

Other than 'entrypoint','cmd' and 'user' you can also set 
the string values for 'workdir'/'workingdir', 'domainname',
'hostname', 'arch'/'architecture' and 'author' in configs.
The values in the env list and label list can be modified too.
Healthcheck can be removed.
If the edit command did not really change something then
the edited image is not loaded back from disk. Instead the 
old image is possibly just tagged with the new name.

For podman it is not possible to check service user examples
and healthcheck examples as it seems to be not supported.
You can globally override the docker tool with --docker=podman, 
or switch to the alternative tool with `PODMAN image1 INTO image2`. 
Using the special `FROM image1 IMPORT image2` commands
you can transfer images between the local storage spaces.

By default the tool will use a local "load.tmp" temporary
directory. You may set "-T $TMPDIR" explicitly to have it
run in a normal temporary directory - but be aware that
the archive files during save/load can be quite big and the
tool will even unpack the archives temporarily. That's why
the "-T tmpdir" should point to a space that is hopefully big
enough (like the build server workspace you are already in).

... **I take patches!** 
... (however please run the `docker-copyedit-tests.py` / `make check` before)
