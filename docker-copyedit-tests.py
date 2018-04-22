#! /usr/bin/python
from __future__ import print_function

__copyright__ = "(C) 2017-2018 Guido U. Draheim, licensed under the EUPL"
__version__ = "1.0.1167"

import subprocess
import unittest
import logging

logg = logging.getLogger("tests")

def sh(cmd = None, shell=True, check = True):
    run = subprocess.Popen(cmd, shell=shell, stdout = subprocess.PIPE, stderr=subprocess.PIPE)
    run.wait()
    if check and run.returncode:
        logg.error("CMD %s", cmd)
        logg.error("EXIT %s", run.returncode)
        logg.error("STDOUT %s", run.stdout.read())
        logg.error("STDERR %s", run.stderr.read())
        raise Exception("shell command failed")
    return run

class Tests(unittest.TestCase):
   def test_001_help(self):
       run = sh("./docker-copyedit.py --help")
       logg.info("help\n%s", run.stdout.read())
   def test_101_fake_simple(self):
       run = sh("./docker-copyedit.py from image1 into image2 --dryrun -vvv")
       logg.info("logs\n%s", run.stderr.read())
   def test_202_real_simple(self):
       run = sh("./docker-copyedit.py from image1 into image2 -vvv")
       logg.info("logs\n%s", run.stderr.read())

if __name__ == "__main__":
    logging.basicConfig(level = logging.INFO)
    unittest.main()
