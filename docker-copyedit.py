#! /usr/bin/env python3
# pylint: disable=missing-module-docstring,invalid-name,wrong-import-position
import sys
import os.path
sys.path = [ os.path.dirname(os.path.abspath(__file__)) ] + sys.path
from docker_copyedit1 import docker_copyedit
docker_copyedit.main()
