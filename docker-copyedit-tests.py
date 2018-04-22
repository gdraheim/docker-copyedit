#! /usr/bin/python
from __future__ import print_function

__copyright__ = "(C) 2017-2018 Guido U. Draheim, licensed under the EUPL"
__version__ = "1.0.1167"

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
        logg.info("help\n%s", run.stdout.read())
    def test_101_fake_simple(self):
        run = sh("./docker-copyedit.py from image1 into image2 --dryrun -vvv")
        logg.info("logs\n%s", run.stderr.read())
    def test_202_real_simple(self):
        run = sh("./docker-copyedit.py from image1 into image2 -vvv")
        logg.info("logs\n%s", run.stderr.read())
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
    def test_400_entrypoint_to_cmd(self):
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
        self.assertEqual(dat2[0]["Config"]["Entrypoint"], None)
        self.assertEqual(dat1[0]["Config"]["Entrypoint"], [u"/entrypoint.sh"])

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
