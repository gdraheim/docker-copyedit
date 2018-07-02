#! /usr/bin/python
from __future__ import print_function

__copyright__ = "(C) 2017-2018 Guido U. Draheim, licensed under the EUPL"
__version__ = "1.1.1271"

import subprocess
import collections
import unittest
import datetime
import re
import time
import inspect
import shutil
import os.path
import logging
from fnmatch import fnmatchcase as fnmatch
import json

logg = logging.getLogger("tests")

OK=True
IMG = "localhost:5000/docker-copyedit"

def get_caller_name():
    frame = inspect.currentframe().f_back.f_back
    return frame.f_code.co_name
def get_caller_caller_name():
    frame = inspect.currentframe().f_back.f_back.f_back
    return frame.f_code.co_name
def os_path(root, path):
    if not root:
        return path
    if not path:
        return path
    while path.startswith(os.path.sep):
       path = path[1:]
    return os.path.join(root, path)

def _lines(lines):
    if isinstance(lines, basestring):
        lines = lines.split("\n")
        if len(lines) and lines[-1] == "":
            lines = lines[:-1]
    return lines
def lines(text):
    lines = []
    for line in _lines(text):
        lines.append(line.rstrip())
    return lines
def grep(pattern, lines):
    for line in _lines(lines):
       if re.search(pattern, line.rstrip()):
           yield line.rstrip()
def greps(lines, pattern):
    return list(grep(pattern, lines))

def text_file(filename, content):
    filedir = os.path.dirname(filename)
    if not os.path.isdir(filedir):
        os.makedirs(filedir)
    f = open(filename, "w")
    if content.startswith("\n"):
        x = re.match("(?s)\n( *)", content)
        indent = x.group(1)
        for line in content[1:].split("\n"):
            if line.startswith(indent):
                line = line[len(indent):]
            f.write(line+"\n")
    else:
        f.write(content)
    f.close()
def shell_file(filename, content):
    text_file(filename, content)
    os.chmod(filename, 0770)

def sh(cmd = None, shell=True, check = True, ok = None, default = ""):
    if ok is None: ok = OK # a parameter "ok = OK" does not work in python
    Result = collections.namedtuple("ShellResult", ["returncode", "stdout", "stderr"])
    if not ok:
        logg.info("skip %s", cmd)
        return Result(0, default, "")
    run = subprocess.Popen(cmd, shell=shell, stdout = subprocess.PIPE, stderr=subprocess.PIPE)
    run.wait()
    result = Result(run.returncode, run.stdout.read(), run.stderr.read())
    if check and result.returncode:
        logg.error("CMD %s", cmd)
        logg.error("EXIT %s", result.returncode)
        logg.error("STDOUT %s", result.stdout)
        logg.error("STDERR %s", result.stderr)
        raise Exception("shell command failed")
    return result

class DockerCopyeditTest(unittest.TestCase):
    def caller_testname(self):
        name = get_caller_caller_name()
        x1 = name.find("_")
        if x1 < 0: return name
        x2 = name.find("_", x1+1)
        if x2 < 0: return name
        return name[:x2]
    def testname(self, suffix = None):
        name = self.caller_testname()
        if suffix:
            return name + "_" + suffix
        return name
    def testdir(self, testname = None):
        testname = testname or self.caller_testname()
        newdir = "tmp/tmp."+testname
        if os.path.isdir(newdir):
            shutil.rmtree(newdir)
        os.makedirs(newdir)
        return newdir
    def rm_testdir(self, testname = None):
        testname = testname or self.caller_testname()
        newdir = "tmp/tmp."+testname
        if os.path.isdir(newdir):
            shutil.rmtree(newdir)
        return newdir
    #
    def test_001_help(self):
        run = sh("./docker-copyedit.py --help")
        logg.info("help\n%s", run.stdout)
    def test_101_fake_simple(self):
        run = sh("./docker-copyedit.py from image1 into image2 --dryrun -vvv")
        logg.info("logs\n%s", run.stderr)
    def test_202_real_simple(self):
        run = sh("./docker-copyedit.py from image1 into image2 -vvv")
        logg.info("logs\n%s", run.stderr)
    def test_301_remove_volumes(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          VOLUME /mydata""")
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove all volumes -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"]["Volumes"], None)
        self.assertEqual(dat1[0]["Config"]["Volumes"], {u"/mydata": {}})
    def test_302_remove_all_volumes(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove all volumes -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"]["Volumes"], None)
        self.assertEqual(dat1[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}})
    def test_303_remove_all_volumes(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat0 = data
        #
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM {img}:{testname}
          RUN touch /myinfo2.txt
          VOLUME /mylogs
          """.format(**locals()))
        cmd = "docker build {testdir} -t {img}:{testname}b"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}b"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}b  VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname}b INTO {img}:{testname}x remove all volumes -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}b {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"]["Volumes"], None)
        self.assertEqual(dat1[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}, u"/mylogs": {}})
        self.assertEqual(dat0[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}})
    def test_310_remove_one_volume(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove volume /myfiles "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"]["Volumes"], {u"/mydata": {}})
        self.assertEqual(dat1[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}})
        self.assertNotEqual(dat1[0]["Id"], dat2[0]["Id"]) # changed
    def test_320_remove_nonexistant_volume(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove volume /nonexistant "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}})
        self.assertEqual(dat1[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}})
        self.assertEqual(dat1[0]["Id"], dat2[0]["Id"]) # unchanged
    def test_350_remove_volumes_by_pattern(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          VOLUME /data
          VOLUME /mydata
          VOLUME /myfiles
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove volumes /my% -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Volumes"], {u"/data": {}, u"/mydata": {}, u"/myfiles": {}})
        self.assertEqual(dat2[0]["Config"]["Volumes"], {u"/data": {} })
        self.assertNotEqual(dat1[0]["Id"], dat2[0]["Id"]) # unchanged
    def test_380_add_new_volume(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x add volume /xtra -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}})
        self.assertEqual(dat2[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}, u"/xtra": {}})
        self.assertNotEqual(dat1[0]["Id"], dat2[0]["Id"]) # unchanged
    def test_390_add_existing_volume(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x add volume /mydata and add volume /xtra -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x VOLUMES = %s", data[0]["Config"]["Volumes"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}})
        self.assertEqual(dat2[0]["Config"]["Volumes"], {u"/mydata": {}, u"/myfiles": {}, u"/xtra": {}})
        self.assertNotEqual(dat1[0]["Id"], dat2[0]["Id"]) # unchanged
    def test_400_remove_all_ports(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 5599
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove all ports -vv "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts","<nonexistant>"))
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts","<nonexistant>"), "<nonexistant>")
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts","<nonexistant>"), {u'4444/tcp': {}, u'5599/tcp': {}})
    def test_410_remove_one_port(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 5599
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove port 4444 -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"]["ExposedPorts"], {u'5599/tcp': {}})
        self.assertEqual(dat1[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}, u'5599/tcp': {}})
    def test_420_remove_one_port(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 389
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove port ldap -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}})
        self.assertEqual(dat1[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}, u'389/tcp': {}})
    def test_430_remove_two_port(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 389
          EXPOSE 636
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x rm port ldap and rm port ldaps -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat2[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}})
        self.assertEqual(dat1[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}, u'389/tcp': {}, u'636/tcp': {}})
    def test_450_remove_ports_by_pattern(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 4499
          EXPOSE 389
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x remove ports 44% -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}, u'4499/tcp': {}, u'389/tcp': {}})
        self.assertEqual(dat2[0]["Config"]["ExposedPorts"], {u'389/tcp': {}})
    def test_480_add_new_port(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          EXPOSE 4444
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x add port ldap and add port ldaps -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}})
        self.assertEqual(dat2[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}, u'389/tcp': {}, u'636/tcp': {}})
    def test_490_add_existing_port(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN touch /myinfo.txt
          EXPOSE 4444
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x add port 4444 and add port ldaps -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname}x ExposedPorts = %s", data[0]["Config"]["ExposedPorts"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}})
        self.assertEqual(dat2[0]["Config"]["ExposedPorts"], {u'4444/tcp': {}, u'636/tcp': {}})
    def test_500_entrypoint_to_cmd(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod +755 /entrypoint.sh
          ENTRYPOINT ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x set entrypoint null and set cmd /entrypoint.sh -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        dat2 = data
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        cmd = "docker run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Entrypoint"], [u"/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat1[0]["Config"]["Cmd"], None)
        self.assertEqual(dat2[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
    def test_510_set_shell_cmd(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo '"$@"'; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod +755 /entrypoint.sh
          ENTRYPOINT ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x set entrypoint null and set shell cmd '/entrypoint.sh foo' -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        dat2 = data
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        cmd = "docker run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Entrypoint"], [u"/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat1[0]["Config"]["Cmd"], None)
        self.assertEqual(dat2[0]["Config"]["Cmd"], [u"/bin/sh", u"-c", u"/entrypoint.sh foo"])
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
    def test_700_keep_user_as_is(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          USER myuser
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat2 = data
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        cmd = "docker run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat2[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat1[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"]["User"], u"myuser")
        self.assertEqual(dat2[0]["Config"]["User"], u"myuser")
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
    def test_710_set_user_null(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          USER myuser
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET USER NULL -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat2 = data
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        cmd = "docker run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat2[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat1[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"]["User"], u"myuser")
        self.assertEqual(dat2[0]["Config"]["User"], u"")
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
    def test_720_set_to_newuser_not_runnable(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody newuser
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          USER myuser
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET USER newuser -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat2 = data
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        cmd = "docker run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat2[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat1[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"]["User"], u"myuser")
        self.assertEqual(dat2[0]["Config"]["User"], u"newuser") # <<<< yayy
        self.assertNotIn("sleep", top1) # <<<< difference to 710
        self.assertNotIn("sleep", top2)
    def test_730_set_to_newuser_being_runnable(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody newuser
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          USER newuser
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET USER myuser -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat2 = data
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        cmd = "docker run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat2[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat1[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"]["User"], u"newuser")
        self.assertEqual(dat2[0]["Config"]["User"], u"myuser") 
        self.assertIn("sleep", top1) # <<<< difference to 720
        self.assertNotIn("sleep", top2)
    def test_750_set_to_numeric_user_being_runnable(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -u 1020 -g nobody newuser
          RUN useradd -u 1030 -g nobody myuser
          RUN chown myuser /entrypoint.sh
          USER newuser
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET USER 1030 -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Entrypoint = %s", data[0]["Config"]["Entrypoint"])
        logg.info("{testname} Cmd = %s", data[0]["Config"]["Cmd"])
        logg.info("{testname} User = %s", data[0]["Config"]["User"])
        dat2 = data
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        cmd = "docker run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = "docker top {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = "docker rm -f {testname}x"
        run = sh(cmd.format(**locals()), check = False)
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat2[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat1[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"]["Cmd"], [u"/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"]["User"], u"newuser")
        self.assertEqual(dat2[0]["Config"]["User"], u"1030") 
        self.assertIn("sleep", top1) # <<<< difference to 720
        self.assertNotIn("sleep", top2)
    def test_800_change_workdir(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} WorkingDir = %s", data[0]["Config"]["WorkingDir"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET workdir /foo -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} WorkingDir = %s", data[0]["Config"]["WorkingDir"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["WorkingDir"], u"/tmp")
        self.assertEqual(dat2[0]["Config"]["WorkingDir"], u"/foo")
    def test_801_change_workingdir(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} WorkingDir = %s", data[0]["Config"]["WorkingDir"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET workingdir /foo -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} WorkingDir = %s", data[0]["Config"]["WorkingDir"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["WorkingDir"], u"/tmp")
        self.assertEqual(dat2[0]["Config"]["WorkingDir"], u"/foo")
    def test_810_change_domainname(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Domainname = %s", data[0]["Config"]["Domainname"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET domainname new.name -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Domainname = %s", data[0]["Config"]["Domainname"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Domainname"], u"")
        self.assertEqual(dat2[0]["Config"]["Domainname"], u"new.name")
    def test_820_change_hostname(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Hostname = %s", data[0]["Config"]["Hostname"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET hostname new.name -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Hostname = %s", data[0]["Config"]["Hostname"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Hostname"], u"")
        self.assertEqual(dat2[0]["Config"]["Hostname"], u"new.name")
    def test_850_change_arch(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g nobody myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Architecture = %s", data[0]["Architecture"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET arch i386 -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} Architecutre = %s", data[0]["Architecture"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Architecture"], u"amd64")
        self.assertEqual(dat2[0]["Architecture"], u"i386")
    def test_900_change_license_label(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          LABEL license free
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("LABELS:\n%s", data[0]["Config"]["Labels"])
        logg.info("{testname} License = %s", data[0]["Config"]["Labels"]["license"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET LABEL license LGPLv2 -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("{testname} License = %s", data[0]["Config"]["Labels"]["license"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Labels"]["license"], u"free")
        self.assertEqual(dat2[0]["Config"]["Labels"]["license"], u"LGPLv2")
    def test_901_change_info_label(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          LABEL info free
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("LABELS:\n%s", data[0]["Config"]["Labels"])
        logg.info("{testname} Info = %s", data[0]["Config"]["Labels"]["info"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET LABEL info new -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Labels"]["info"], u"free")
        self.assertEqual(dat2[0]["Config"]["Labels"]["info"], u"new")
    def test_910_remove_other_label(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          LABEL info free
          LABEL other text
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("LABELS:\n%s", data[0]["Config"]["Labels"])
        logg.info("{testname} Info = %s", data[0]["Config"]["Labels"]["info"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x REMOVE LABEL other -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Labels"]["other"], u"text")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("other", "<nonexistant>"), u"<nonexistant>")
    def test_920_remove_info_labels(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          LABEL info1 free
          LABEL other text
          LABEL info2 next
          LABEL MORE info
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("LABELS:\n%s", data[0]["Config"]["Labels"])
        logg.info("{testname} Info1 = %s", data[0]["Config"]["Labels"]["info1"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x REMOVE LABELS info% -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertEqual(dat1[0]["Config"]["Labels"]["info1"], u"free")
        self.assertEqual(dat1[0]["Config"]["Labels"]["info2"], u"next")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("info1", "<nonexistant>"), u"<nonexistant>")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("info2", "<nonexistant>"), u"<nonexistant>")
        self.assertEqual(dat2[0]["Config"]["Labels"]["other"], u"text")
        self.assertEqual(dat2[0]["Config"]["Labels"]["MORE"], u"info")
    def test_950_change_info_env(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          ENV INFO free
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("Env:\n%s", data[0]["Config"]["Env"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x SET ENV INFO new -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertIn("INFO=free", dat1[0]["Config"]["Env"])
        self.assertIn("INFO=new", dat2[0]["Config"]["Env"])
    def test_960_remove_other_env(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          ENV INFO free
          ENV OTHER text
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("Env:\n%s", data[0]["Config"]["Env"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x REMOVE ENV OTHER -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertIn("INFO=free", dat1[0]["Config"]["Env"])
        self.assertNotIn("OTHER=text", dat2[0]["Config"]["Env"])
    def test_970_remove_info_envs(self):
        img = IMG
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"),"""
          FROM centos:centos7
          RUN { echo "#! /bin/sh"; echo "exec sleep 4"; } > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          ENV INFO1 free
          ENV OTHER text
          ENV INFO2 next
          ENV MORE  info
          CMD ["/entrypoint.sh"]
          """)
        cmd = "docker build {testdir} -t {img}:{testname}"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.info("Env:\n%s", data[0]["Config"]["Env"])
        dat1 = data
        #
        cmd = "./docker-copyedit.py FROM {img}:{testname} INTO {img}:{testname}x REMOVE ENVS INFO% -vv"
        run = sh(cmd.format(**locals()))
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = "docker inspect {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = "docker rmi {img}:{testname} {img}:{testname}x"
        run = sh(cmd.format(**locals()))
        logg.info("[%s] %s", run.returncode, cmd.format(**locals()))
        #
        self.assertIn("INFO1=free", dat1[0]["Config"]["Env"])
        self.assertIn("INFO2=next", dat1[0]["Config"]["Env"])
        self.assertNotIn("INFO1=free", dat2[0]["Config"]["Env"])
        self.assertNotIn("INFO2=next", dat2[0]["Config"]["Env"])
        self.assertIn("OTHER=text", dat1[0]["Config"]["Env"])
        self.assertIn("OTHER=text", dat2[0]["Config"]["Env"])
        self.assertIn("MORE=info", dat1[0]["Config"]["Env"])

if __name__ == "__main__":
    ## logging.basicConfig(level = logging.INFO)
    ## unittest.main()
    from optparse import OptionParser
    _o = OptionParser("%prog [options] test*")
    _o.add_option("-v","--verbose", action="count", default=0,
       help="increase logging level [%default]")
    _o.add_option("--xmlresults", metavar="FILE", default=None,
       help="capture results as a junit xml file [%default]")
    opt, args = _o.parse_args()
    logging.basicConfig(level = logging.WARNING - opt.verbose * 5)
    suite = unittest.TestSuite()
    if not args: args = [ "test_*" ]
    for arg in args:
        for classname in sorted(globals()):
            if not classname.endswith("Test"):
                continue
            testclass = globals()[classname]
            for method in sorted(dir(testclass)):
                if "*" not in arg: arg += "*"
                if arg.startswith("_"): arg = arg[1:]
                if fnmatch(method, arg):
                    suite.addTest(testclass(method))
    # running
    xmlresults = None
    if opt.xmlresults:
        if os.path.exists(opt.xmlresults):
           os.remove(opt.xmlresults)
        xmlresults = open(opt.xmlresults, "w")
        logg.info("xml results into %s", opt.xmlresults)
    if xmlresults:
        import xmlrunner
        Runner = xmlrunner.XMLTestRunner
        Runner(xmlresults).run(suite)
    else:
        Runner = unittest.TextTestRunner
        Runner(verbosity=opt.verbose).run(suite)
