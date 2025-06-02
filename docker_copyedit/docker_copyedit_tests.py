#! /usr/bin/env python3
# pylint: disable=missing-module-docstring,missing-class-docstring,missing-function-docstring,line-too-long,too-many-lines,multiple-statements
# pylint: disable=invalid-name,unspecified-encoding,redefined-outer-name,unused-variable
# pylint: disable=consider-using-with,too-many-locals,too-many-statements,too-many-public-methods

__copyright__ = "(C) 2017-2025 Guido U. Draheim, licensed under the EUPL"
__version__ = "1.5.1221"

from typing import Optional, Union, List, Iterator, NamedTuple
import sys
import subprocess
import unittest
import re
import time
import inspect
import shutil
import os.path
import glob
import logging
from fnmatch import fnmatchcase as fnmatch
import json

os.chdir(os.path.dirname(os.path.abspath(__file__)))  # assume the scripts stayed together

logg = logging.getLogger("tests")

OK = True
IMG = "localhost:5000/docker-copyedit"
UID = 1001
TMP = "tmp"

_python = "python"
_docker = "docker"
_podman = ""  # usually "podman"
_script = "docker_copyedit.py"
_force = 0
_keep = 0
_image = "almalinux:9.5-20250307"
_coverage = False
_coverage_file = "tmp.coverage.xml"

def _copyedit(docker: Optional[str] = None) -> str:
    docker = docker or _docker
    script = _script
    if docker != "docker":
        script += " --docker=" + docker
    if _coverage:
        script = "-m coverage run -a " + script
    return script
def _centos() -> str:
    return _image
def _nogroup(image: Optional[str] = None) -> str:
    image = image or _image
    if "centos" in image:
        return "nobody"
    if "ubuntu" in image:
        return "nogroup"
    return "nobody"

def get_caller_name() -> str:
    currentframe = inspect.currentframe()
    if currentframe is None:
        return "global"
    if currentframe.f_back is None:
        return "global"
    if currentframe.f_back.f_back is None:
        return "global"
    frame = currentframe.f_back.f_back
    return frame.f_code.co_name
def get_caller_caller_name() -> str:
    currentframe = inspect.currentframe()
    if currentframe is None:
        return "global"
    if currentframe.f_back is None:
        return "global"
    if currentframe.f_back.f_back is None:
        return "global"
    if currentframe.f_back.f_back.f_back is None:
        return "global"
    frame = currentframe.f_back.f_back.f_back
    return frame.f_code.co_name
def get_caller_caller_caller_name() -> str:
    currentframe = inspect.currentframe()
    if currentframe is None:
        return "global"
    if currentframe.f_back is None:
        return "global"
    if currentframe.f_back.f_back is None:
        return "global"
    if currentframe.f_back.f_back.f_back is None:
        return "global"
    if currentframe.f_back.f_back.f_back.f_back is None:
        return "global"
    frame = currentframe.f_back.f_back.f_back.f_back
    return frame.f_code.co_name
def os_path(root: Optional[str], path: str) -> str:
    if not root:
        return path
    if not path:
        return path
    while path.startswith(os.path.sep):
        path = path[1:]
    return os.path.join(root, path)
def decodes(text: Union[None, bytes, str]) -> Optional[str]:
    if text is None: return None
    if isinstance(text, bytes):
        encoded = sys.getdefaultencoding()
        if encoded in ["ascii"]:
            encoded = "utf-8"
        try:
            return text.decode(encoded)
        except UnicodeDecodeError:
            return text.decode("latin-1")
    return text

def _lines(lines: Union[str, List[str]]) -> List[str]:
    if isinstance(lines, str):
        lines = lines.split("\n")
        if len(lines) and lines[-1] == "":
            lines = lines[:-1]
    return lines
def lines(text: Union[str, List[str]]) -> List[str]:
    lines = []
    for line in _lines(text):
        lines.append(line.rstrip())
    return lines
def _grep(pattern: str, lines: Union[str, List[str]]) -> Iterator[str]:
    for line in _lines(lines):
        if re.search(pattern, line.rstrip()):
            yield line.rstrip()
def grep(pattern: str, lines: Union[str, List[str]]) -> List[str]:
    return list(grep(pattern, lines))
def greps(lines: Union[str, List[str]], pattern: str) -> List[str]:
    return list(grep(pattern, lines))

def text_file(filename: str, content: str) -> None:
    filedir = os.path.dirname(filename)
    if not os.path.isdir(filedir):
        os.makedirs(filedir)
    f = open(filename, "w")
    if content.startswith("\n"):
        x = re.match("(?s)\n( *)", content)
        assert x is not None
        indent = x.group(1)
        for line in content[1:].split("\n"):
            if line.startswith(indent):
                line = line[len(indent):]
            f.write(line + "\n")
    else:
        f.write(content)
    f.close()
def shell_file(filename: str, content: str) -> None:
    text_file(filename, content)
    os.chmod(filename, 0o770)

class ShellResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str
class ShellException(Exception):
    def __init__(self, msg: str, result: ShellResult) -> None:
        Exception.__init__(self, msg)
        self.result = result
def sh(cmd: str, shell: bool = True, check: bool = True, ok: Optional[bool] = None, default: str = "") -> ShellResult:
    if ok is None: ok = OK  # a parameter "ok = OK" does not work in python
    if not ok:
        logg.info("skip %s", cmd)
        return ShellResult(0, default or "", "")
    run = subprocess.Popen(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run.wait()
    assert run.stdout is not None and run.stderr is not None
    result = ShellResult(run.returncode, decodes(run.stdout.read()) or "", decodes(run.stderr.read()) or "")
    if check and result.returncode:
        logg.error("CMD %s", cmd)
        logg.error("EXIT %s", result.returncode)
        logg.error("STDOUT %s", result.stdout)
        logg.error("STDERR %s", result.stderr)
        raise ShellException("shell command failed", result)
    return result

class DockerCopyeditTest(unittest.TestCase):
    def caller_testname(self) -> str:
        name = get_caller_caller_name()
        nested = get_caller_caller_caller_name()
        if nested.startswith("test_"):
            name = nested
        x1 = name.find("_")
        if x1 < 0: return name
        x2 = name.find("_", x1 + 1)
        if x2 < 0: return name
        return name[:x2]
    def testname(self, suffix: Optional[str] = None) -> str:
        name = self.caller_testname()
        if suffix:
            return name + "_" + suffix
        return name
    def testdir(self, testname: Optional[str] = None) -> str:
        testname = testname or self.caller_testname()
        newdir = os.path.join(TMP, testname)
        if os.path.isdir(newdir):
            shutil.rmtree(newdir)
        os.makedirs(newdir)
        return newdir
    def rm_testdir(self, testname: Optional[str] = None) -> str:
        testname = testname or self.caller_testname()
        newdir = os.path.join(TMP, testname)
        if os.path.isdir(newdir):
            if _keep:
                logg.info("KEEP %s", newdir)
            else:
                shutil.rmtree(newdir)
        return newdir
    def save(self, testname: str) -> None:
        if os.path.exists(".coverage"):
            os.rename(".coverage", os.path.join(TMP, ".coverage." + testname))
    def can_not_chown(self, docker: str) -> Optional[str]:
        if _force:
            return None
        if docker.endswith("podman"):  # may check for a specific version?
            return "`podman build` can not run `chown myuser` steps"
        return None
    def healthcheck_not_supported(self, docker: str) -> Optional[str]:
        if _force:
            return None
        if docker.endswith("podman"):  # may check for a specific version?
            return "`podman build` can support HEALTHCHECK CMD settings"
        return None
    def no_podman(self) -> str:
        podman = _podman
        if not podman:
            return "no --podman=alternative tool specified"
        if podman == _docker:
            return "found same docker and alternative tool"
        if os.path.exists(podman):
            return ""
        if "/" not in podman:
            for check in os.environ.get("PATH", "/usr/bin").split(":"):
                if os.path.exists(os.path.join(check, podman)):
                    return ""
        return F"did not find alternative tool = {podman}"
    #
    def test_011_help(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py --help """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        cmd = F"{python} {copyedit} --help"
        run = sh(cmd)
        logg.info("help\n%s", run.stdout)
    def test_012_help(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py --help """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        cmd = F"{python} {copyedit} --help"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
    def test_014_help(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py --help """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        try:
            cmd = F"{python} {copyedit} --helps"
            run = sh(cmd)
            logg.info("help\n%s", run.stdout)
        except Exception as e: # pylint: disable=broad-exception-caught
            msg = str(e)
            logg.info("help exception %s", msg)
            self.assertEqual(msg, "shell command failed")
    def test_101_fake_simple(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 --dryrun """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        cmd = F"{python} {copyedit} from image1 into image2 --dryrun -vvv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        self.save(self.testname())
    def test_102_fake_simple(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1  --dryrun """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        cmd = F"{python} {copyedit} from image1 --dryrun -vvv"
        try:
            run = sh(cmd)
        except ShellException as e:
            logg.info("catch %s", e)
            self.assertIn("no output image given - use 'INTO image-name'", e.result.stderr)
            run = e.result
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        self.save(self.testname())
    def test_103_fake_simple(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into '' --dryrun """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        cmd = F"{python} {copyedit} from image1 into '' --dryrun -vvv"
        try:
            run = sh(cmd)
        except ShellException as e:
            logg.info("catch %s", e)
            self.assertIn("no output image given - use 'INTO image-name'", e.result.stderr)
            run = e.result
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        self.save(self.testname())
    def test_104_fake_simple(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into ' ' --dryrun """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        cmd = F"{python} {copyedit} from image1 into ' ' --dryrun -vvv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        self.save(self.testname())
    def test_105_fake_simple(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into ' ' add note x --dryrun """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        cmd = F"{python} {copyedit} from image1 into ' ' add note x --dryrun -vvv"
        try:
            run = sh(cmd)
        except ShellException as e:
            logg.info("catch %s", e)
            self.assertIn("unknown edit command starting with add note", e.result.stderr)
            run = e.result
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        self.save(self.testname())
    def test_118_pull_base_image(self) -> None:
        if self.no_podman(): self.skipTest(self.no_podman())
        self.test_112_pull_base_image(_podman)
    def test_112_pull_base_image(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        cmd = F"{docker} image history {centos} || {docker} pull {centos}"
        logg.info("%s ===========>>>", cmd)
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        if "there might not be enough IDs available in the namespace" in run.stderr:
            logg.error("you need to check /etc/subgid and /etc/subuid")
            logg.error("you need to run : podman system migrate --log-level=debug")
        self.save(self.testname())
    def test_202_real_simple(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 """
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        logg.info(": %s", python)
        cmd = F"{python} {copyedit} from image1 into image2 -vvv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        self.assertIn("nothing to do for image2", run.stderr)
        self.save(self.testname())
    def test_218_can_build(self) -> None:
        if self.no_podman(): self.skipTest(self.no_podman())
        self.test_211_can_build(_podman)
    def test_211_can_build(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{docker} rmi {img}:{testname}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.rm_testdir()
        self.save(testname)
    def test_221_run_unchanged_copyedit(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        savename = testname + "x"
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        self.rm_testdir()
        self.save(testname)
    def test_231_run_version_too_long(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        savename = testname + "-has-image-name-with-a-version-longer-than-one-hundred-twenty-seven-characters"
        savename += "-which-is-not-allowed-for-any-docker-image"
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        self.assertIn("image version: may not be longer", run.stderr)
        self.rm_testdir()
        self.save(testname)
    def test_232_run_version_not_too_long(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        savename = testname + "-has-image-name-with-a-version-shorter-than-one-hundred-twenty-seven-characters"
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        self.assertNotIn("image version: may not be longer", run.stderr)
        self.rm_testdir()
        self.save(testname)
    def test_233_run_version_made_too_long(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        savename = testname + "-has-image-name-with-a-version-shorter-than-one-hundred-twenty-seven-characters"
        cmd = F"{python} {copyedit} -c MAX_VERSION=33 FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        self.assertIn("image version: may not be longer", run.stderr)
        self.rm_testdir()
        self.save(testname)
    def test_280_change_tempdir(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertNotIn("keeping " + datadir, run.stderr)
        self.assertNotIn("keeping " + savetar, run.stderr)
        self.assertNotIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {docker} save", run.stderr)
        self.assertFalse(os.path.isdir(datadir))
        self.assertFalse(os.path.isfile(savetar))
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        self.rm_testdir()
        self.save(testname)
    def test_281_keep_datadir(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} -k FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertIn("keeping " + datadir, run.stderr)
        self.assertNotIn("keeping " + savetar, run.stderr)
        self.assertNotIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {docker} save", run.stderr)
        self.assertTrue(os.path.isdir(datadir))
        self.assertFalse(os.path.isfile(savetar))
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        self.rm_testdir()
        self.save(testname)
    def test_282_keep_savefile(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} -kk FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertIn("keeping " + datadir, run.stderr)
        self.assertNotIn("keeping " + savetar, run.stderr)
        self.assertNotIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {savetar}", run.stderr)
        self.assertTrue(os.path.isdir(datadir))
        self.assertFalse(os.path.isfile(savetar))
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        self.rm_testdir()
        self.save(testname)
    def test_283_keep_inputfile(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} -kkk FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertIn("keeping " + datadir, run.stderr)
        self.assertIn("keeping " + savetar, run.stderr)
        self.assertNotIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {savetar}", run.stderr)
        self.assertTrue(os.path.isdir(datadir))
        self.assertTrue(os.path.isfile(savetar))
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        self.rm_testdir()
        self.save(testname)
    def test_284_keep_outputfile(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} -kkkk FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertIn("keeping " + datadir, run.stderr)
        self.assertIn("keeping " + savetar, run.stderr)
        self.assertIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {savetar}", run.stderr)
        self.assertTrue(os.path.isdir(datadir))
        self.assertTrue(os.path.isfile(savetar))
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        self.rm_testdir()
        self.save(testname)
    def test_291_config_keep_datadir(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} -c KEEPDATADIR=1 FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertIn("keeping " + datadir, run.stderr)
        self.assertNotIn("keeping " + savetar, run.stderr)
        self.assertNotIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {docker} save", run.stderr)
        self.assertTrue(os.path.isdir(datadir))
        self.assertFalse(os.path.isfile(savetar))
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        # self.assertIn(savetar + " (not created)", run.stderr)
        # self.assertIn(loadtar + " (not created)", run.stderr)
        self.rm_testdir()
        self.save(testname)
    def test_292_config_keep_savefile(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} -c KEEPSAVEFILE=1 FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertNotIn("keeping " + datadir, run.stderr)
        self.assertNotIn("keeping " + savetar, run.stderr)
        self.assertNotIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {savetar}", run.stderr)
        self.assertFalse(os.path.isdir(datadir))
        self.assertFalse(os.path.isfile(savetar))
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        # self.assertIn(savetar + " (not created)", run.stderr)
        # self.assertIn(loadtar + " (not created)", run.stderr)
        self.rm_testdir()
        self.save(testname)
    def test_293_config_keep_inputfile(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} -c KEEPINPUTFILE=1 FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertNotIn("keeping " + datadir, run.stderr)
        self.assertIn("keeping " + savetar, run.stderr)
        self.assertNotIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {docker} save", run.stderr)
        self.assertFalse(os.path.isdir(datadir))
        self.assertFalse(os.path.isfile(savetar))  # was not created
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        self.assertIn(savetar + " (not created)", run.stderr)
        # self.assertIn(loadtar + " (not created)", run.stderr)
        self.rm_testdir()
        self.save(testname)
    def test_294_config_keep_outputfile(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        tempdir = testdir + "/new.tmp"
        savename = testname + "x"
        cmd = F"{python} {copyedit} -T {tempdir} -c KEEPOUTPUTFILE=1 FROM {img}:{testname} INTO {img}:{savename} remove label version -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{savename}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), None)
        self.assertIn("there was no label version", run.stderr)
        self.assertIn("unchanged image", run.stderr)
        self.assertIn("tagged old image", run.stderr)
        #
        datadir = tempdir + "/data"
        savetar = tempdir + "/saved.tar"
        loadtar = tempdir + "/ready.tar"
        self.assertIn(datadir, run.stderr)
        self.assertNotIn("keeping " + datadir, run.stderr)
        self.assertNotIn("keeping " + savetar, run.stderr)
        self.assertIn("keeping " + loadtar, run.stderr)
        self.assertIn(F"new {datadir} from {docker} save", run.stderr)
        self.assertFalse(os.path.isdir(datadir))
        self.assertFalse(os.path.isfile(savetar))  # was not created
        self.assertFalse(os.path.isfile(loadtar))  # not packed because no change
        # self.assertIn(savetar + " (not created)", run.stderr)
        self.assertIn(loadtar + " (not created)", run.stderr)
        self.rm_testdir()
        self.save(testname)
    def test_301_remove_volumes(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove all volumes """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          VOLUME /mydata
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove all volumes -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("Volumes"), None)
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/mydata": {}})
        self.rm_testdir()
        self.save(testname)
    def test_302_remove_all_volumes(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove all volumes """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove all volumes -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("Volumes"), None)
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}})
        self.rm_testdir()
        self.save(testname)
    def test_303_remove_all_volumes(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove all volumes """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat0 = data
        #
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {img}:{testname}
          RUN touch /myinfo2.txt
          VOLUME /mylogs
          """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}b"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}b"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}b  VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} -kk FROM {img}:{testname}b INTO {img}:{testname}x remove all volumes -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}b {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("Volumes"), None)
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}, "/mylogs": {}})
        self.assertEqual(dat0[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}})
        self.rm_testdir()
        self.save(testname)
    def test_304_remove_all_volumes_mysql(self, docker: Optional[str] = None) -> None:
        """ remove all volumes (in uppercase) - related to bug report #4 """
        img = "mysql"
        ver = "5.6"
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s %s", python, img, ver)
        testname = self.testname()
        testdir = self.testdir()
        cmd = F"{docker} pull {img}:{ver}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{ver}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{img}:{ver} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{ver} INTO {img}-{testname}:{ver} -vv REMOVE ALL VOLUMES --dryrun"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{python} {copyedit} FROM {img}:{ver} INTO {img}-{testname}:{ver} -vv REMOVE ALL VOLUMES"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}-{testname}:{ver}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{img}-{testname}:{ver} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}-{testname}:{ver}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        cmd = F": docker rmi {img}:{ver}"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("Volumes"), None)
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/var/lib/mysql": {}})
        self.rm_testdir()
        self.save(testname)
    def test_310_remove_one_volume(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove volume /myfiles """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove volume /myfiles "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("Volumes"), {"/mydata": {}})
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}})
        self.assertNotEqual(dat1[0]["Id"], dat2[0]["Id"])  # changed
        self.rm_testdir()
        self.save(testname)
    def test_320_remove_nonexistant_volume(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove volume /nonexistant """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove volume /nonexistant "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}})
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}})
        self.assertEqual(dat1[0]["Id"], dat2[0]["Id"])  # unchanged
        self.rm_testdir()
        self.save(testname)
    def test_350_remove_volumes_by_pattern(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove volumes /my% """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          VOLUME /data
          VOLUME /mydata
          VOLUME /myfiles
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove volumes /my% -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/data": {}, "/mydata": {}, "/myfiles": {}})
        self.assertEqual(dat2[0]["Config"].get("Volumes"), {"/data": {}})
        self.assertNotEqual(dat1[0]["Id"], dat2[0]["Id"])  # unchanged
        self.rm_testdir()
        self.save(testname)
    def test_380_add_new_volume(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 add volume /xtra """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x add volume /xtra -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}})
        self.assertEqual(dat2[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}, "/xtra": {}})
        self.assertNotEqual(dat1[0]["Id"], dat2[0]["Id"])  # unchanged
        self.rm_testdir()
        self.save(testname)
    def test_390_add_existing_volume(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 add volume /mydata and add volume /xtra """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          VOLUME /mydata
          VOLUME /myfiles
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x add volume /mydata and add volume /xtra -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x VOLUMES = %s", data[0]["Config"].get("Volumes"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}})
        self.assertEqual(dat2[0]["Config"].get("Volumes"), {"/mydata": {}, "/myfiles": {}, "/xtra": {}})
        self.assertNotEqual(dat1[0]["Id"], dat2[0]["Id"])  # unchanged
        self.rm_testdir()
        self.save(testname)
    def test_400_remove_all_ports(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove all ports """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 5599
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove all ports -vv "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts", "<nonexistant>"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts", "<nonexistant>"), "<nonexistant>")
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts", "<nonexistant>"), {'4444/tcp': {}, '5599/tcp': {}})
        self.rm_testdir()
        self.save(testname)
    def test_410_remove_one_port_by_number(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove port 4444 """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 5599
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove port 4444 -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts"), {'5599/tcp': {}})
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}, '5599/tcp': {}})
        self.rm_testdir()
        self.save(testname)
    def test_415_remove_one_port_by_number_into_latest(self, docker: Optional[str] = None) -> None:
        """ remove port 4444 (in uppercase) - this is related to issue #5 """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 5599
        """)
        cmd = F"{docker} build {testdir} -t {img}-{testname}:latest"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}-{testname}:latest"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}-{testname}:latest INTO {img}-{testname} REMOVE PORT 4444 -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}-{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}-{testname}:latest"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        cmd = F"{docker} rmi {img}-{testname}"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts"), {'5599/tcp': {}})
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}, '5599/tcp': {}})
        self.rm_testdir()
        self.save(testname)
    def test_420_remove_one_port_by_name(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove port ldap """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 389
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove port ldap -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}})
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}, '389/tcp': {}})
        self.rm_testdir()
        self.save(testname)
    def test_430_remove_two_port(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 rm port ldap and rm port ldaps """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 389
          EXPOSE 636
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x rm port ldap and rm port ldaps -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}})
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}, '389/tcp': {}, '636/tcp': {}})
        self.rm_testdir()
        self.save(testname)
    def test_450_remove_ports_by_pattern(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove ports 44% """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          EXPOSE 4444
          EXPOSE 4499
          EXPOSE 389
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove ports 44% -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}, '4499/tcp': {}, '389/tcp': {}})
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts"), {'389/tcp': {}})
        self.rm_testdir()
        self.save(testname)
    def test_480_add_new_port(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 add port ldap and add port ldaps """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          EXPOSE 4444
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x add port ldap and add port ldaps -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}})
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}, '389/tcp': {}, '636/tcp': {}})
        self.rm_testdir()
        self.save(testname)
    def test_490_add_existing_port(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 add port 4444 and add port ldaps """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          EXPOSE 4444
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x add port 4444 and add port ldaps -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname}x ExposedPorts = %s", data[0]["Config"].get("ExposedPorts"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}})
        self.assertEqual(dat2[0]["Config"].get("ExposedPorts"), {'4444/tcp': {}, '636/tcp': {}})
        self.rm_testdir()
        self.save(testname)
    def test_500_entrypoint_to_cmd(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set null entrypoint and set cmd /entrypoint.sh """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod +755 /entrypoint.sh
          ENTRYPOINT ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x set null entrypoint and set cmd /entrypoint.sh -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), None)
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_505_entrypoint_to_cmd_old_null(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set entrypoint null and set cmd /entrypoint.sh (deprecated) """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod +755 /entrypoint.sh
          ENTRYPOINT ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x set entrypoint null and set cmd /entrypoint.sh -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), None)
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_510_set_shell_cmd(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set null entrypoint and set shell cmd '/entrypoint.sh foo' """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo '"$@"'; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod +755 /entrypoint.sh
          ENTRYPOINT ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x set null entrypoint and set shell cmd '/entrypoint.sh foo' -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), None)
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/bin/sh", "-c", "/entrypoint.sh foo"])
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_515_set_shell_cmd_old_null(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set entrypoint null and set shell cmd '/entrypoint.sh foo' (deprecated) """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo '"$@"'; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod +755 /entrypoint.sh
          ENTRYPOINT ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x set entrypoint null and set shell cmd '/entrypoint.sh foo' -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), None)
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/bin/sh", "-c", "/entrypoint.sh foo"])
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_601_remove_healthcheck(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        if self.healthcheck_not_supported(docker): self.skipTest(self.healthcheck_not_supported(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
          HEALTHCHECK CMD '[[ -f /myinfo.txt ]]'
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} HEALTHCHECK = %s", data[0]["Config"].get("Healtcheck"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove healthcheck -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertNotIn("Healthcheck", dat2[0]["Config"])
        self.assertIn("Healthcheck", dat1[0]["Config"])
        self.rm_testdir()
        self.save(testname)
    def test_602_remove_nonexistant_healthcheck(self, docker: Optional[str] = None) -> None:
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN touch /myinfo.txt
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x remove healthcheck -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertNotIn("Healthcheck", dat2[0]["Config"])
        self.assertNotIn("Healthcheck", dat1[0]["Config"])
        self.rm_testdir()
        self.save(testname)
    def test_700_keep_user_as_is(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 (same user) """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        uid = UID
        me = os.getuid()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} -u {uid} myuser
          RUN chown myuser /entrypoint.sh
          USER myuser
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"].get("User"), "myuser")
        self.assertEqual(dat2[0]["Config"].get("User"), "myuser")
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_710_set_null_user(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set null user """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          USER myuser
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET NULL USER -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"].get("User"), "myuser")
        self.assertEqual(dat2[0]["Config"].get("User"), "")
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_711_set_no_user(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set null user (in uppercase)"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          USER myuser
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET NULL USER -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"].get("User"), "myuser")
        self.assertEqual(dat2[0]["Config"].get("User"), "")
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_715_set_user_null_old_null(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set user null (deprecated)"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          USER myuser
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET USER NULL -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"].get("User"), "myuser")
        self.assertEqual(dat2[0]["Config"].get("User"), "")
        self.assertIn("sleep", top1)
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_720_set_to_newuser_not_runnable(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set user newuser"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} newuser
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          USER myuser
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET USER newuser -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"].get("User"), "myuser")
        self.assertEqual(dat2[0]["Config"].get("User"), "newuser")  # <<<< yayy
        self.assertNotIn("sleep", top1)  # <<<< difference to 710
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_730_set_to_newuser_being_runnable(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set user myuser"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} newuser
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          USER newuser
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET USER myuser -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"].get("User"), "newuser")
        self.assertEqual(dat2[0]["Config"].get("User"), "myuser")
        self.assertIn("sleep", top1)  # <<<< difference to 720
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_750_set_to_numeric_user_being_runnable(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set user 1030"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -u 1020 -g {nogroup} newuser
          RUN useradd -u 1030 -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          USER newuser
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET USER 1030 -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Entrypoint = %s", data[0]["Config"].get("Entrypoint"))
        logg.info(F"{testname} Cmd = %s", data[0]["Config"].get("Cmd"))
        logg.info(F"{testname} User = %s", data[0]["Config"].get("User"))
        dat2 = data
        #
        cmd = F"{docker} rm -f {testname}x"
        run = sh(cmd, check=False)
        cmd = F"{docker} run --name {testname}x -d {img}:{testname}x "
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top1 = run.stdout
        logg.info("wait till finished")
        time.sleep(4)
        cmd = F"{docker} top {testname}x"
        run = sh(cmd, check=False)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        top2 = run.stdout
        #
        cmd = F"{docker} rm -f {testname}x"
        rmi = sh(cmd, check=False)
        logg.info("[%s] %s", rmi.returncode, cmd)
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat2[0]["Config"].get("Entrypoint"), None)
        self.assertEqual(dat1[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat2[0]["Config"].get("Cmd"), ["/entrypoint.sh"])
        self.assertEqual(dat1[0]["Config"].get("User"), "newuser")
        self.assertEqual(dat2[0]["Config"].get("User"), "1030")
        self.assertIn("sleep", top1)  # <<<< difference to 720
        self.assertNotIn("sleep", top2)
        self.rm_testdir()
        self.save(testname)
    def test_800_change_workdir(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set workdir /foo"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} WorkingDir = %s", data[0]["Config"].get("WorkingDir"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET workdir /foo -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} WorkingDir = %s", data[0]["Config"].get("WorkingDir"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("WorkingDir"), "/tmp")
        self.assertEqual(dat2[0]["Config"].get("WorkingDir"), "/foo")
        self.rm_testdir()
        self.save(testname)
    def test_801_change_workingdir(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set workingdir /foo"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} WorkingDir = %s", data[0]["Config"].get("WorkingDir"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET workingdir /foo -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} WorkingDir = %s", data[0]["Config"].get("WorkingDir"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("WorkingDir"), "/tmp")
        self.assertEqual(dat2[0]["Config"].get("WorkingDir"), "/foo")
        self.rm_testdir()
        self.save(testname)
    def test_810_change_domainname(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set domainname new.name"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Domainname = %s", data[0]["Config"].get("Domainname"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET domainname new.name -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Domainname = %s", data[0]["Config"].get("Domainname"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Domainname"), "")
        self.assertEqual(dat2[0]["Config"].get("Domainname"), "new.name")
        self.rm_testdir()
        self.save(testname)
    def test_820_change_hostname(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set hostname new.name"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Hostname = %s", data[0]["Config"].get("Hostname"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET hostname new.name -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Hostname = %s", data[0]["Config"].get("Hostname"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"].get("Hostname"), "")
        self.assertEqual(dat2[0]["Config"].get("Hostname"), "new.name")
        self.rm_testdir()
        self.save(testname)
    def test_850_change_arch(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set arch i386"""
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        nogroup = _nogroup()
        logg.info(": %s : %s", python, img)
        if self.can_not_chown(docker): self.skipTest(self.can_not_chown(docker))
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          RUN useradd -g {nogroup} myuser
          RUN chown myuser /entrypoint.sh
          WORKDIR /tmp
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Architecture = %s", data[0]["Architecture"])
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET arch i386 -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info(F"{testname} Architecutre = %s", data[0]["Architecture"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Architecture"], "amd64")
        self.assertEqual(dat2[0]["Architecture"], "i386")
        self.rm_testdir()
        self.save(testname)
    def test_900_change_license_label(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set label license LGPLv2 """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          LABEL license free
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("LABELS:\n%s", data[0]["Config"].get("Labels"))
        logg.info(F"{testname} License = %s", data[0]["Config"]["Labels"].get("license"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET LABEL license LGPLv2 -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        logg.info("LABELS:\n%s", data[0]["Config"].get("Labels"))
        logg.info(F"{testname} License = %s", data[0]["Config"]["Labels"].get("license"))
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"]["Labels"].get("license"), "free")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("license"), "LGPLv2")
        self.rm_testdir()
        self.save(testname)
    def test_901_change_info_label(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set label info new """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          LABEL info free
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("LABELS:\n%s", data[0]["Config"].get("Labels"))
        logg.info(F"{testname} Info = %s", data[0]["Config"]["Labels"].get("info"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET LABEL info new -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"]["Labels"].get("info"), "free")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("info"), "new")
        self.rm_testdir()
        self.save(testname)
    def test_910_remove_other_label(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove label other """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          LABEL info free
          LABEL other text
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("LABELS:\n%s", data[0]["Config"].get("Labels"))
        logg.info(F"{testname} Info = %s", data[0]["Config"]["Labels"].get("info"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x REMOVE LABEL other -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"]["Labels"].get("other"), "text")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("other", "<nonexistant>"), "<nonexistant>")
        self.rm_testdir()
        self.save(testname)
    def test_911_remove_info_labels(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove labels info% """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          LABEL info1 free
          LABEL other text
          LABEL info2 next
          LABEL MORE info
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("LABELS:\n%s", data[0]["Config"].get("Labels"))
        logg.info(F"{testname} Info1 = %s", data[0]["Config"]["Labels"].get("info1"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x REMOVE LABELS info% -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertEqual(dat1[0]["Config"]["Labels"].get("info1"), "free")
        self.assertEqual(dat1[0]["Config"]["Labels"].get("info2"), "next")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("info1", "<nonexistant>"), "<nonexistant>")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("info2", "<nonexistant>"), "<nonexistant>")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("other"), "text")
        self.assertEqual(dat2[0]["Config"]["Labels"].get("MORE"), "info")
        self.rm_testdir()
        self.save(testname)
    def test_920_change_info_env(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set env info new """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          ENV INFO free
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("Env:\n%s", data[0]["Config"].get("Env"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET ENV INFO new -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertIn("INFO=free", dat1[0]["Config"].get("Env"))
        self.assertIn("INFO=new", dat2[0]["Config"].get("Env"))
        self.rm_testdir()
        self.save(testname)
    def test_921_change_info_envs(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 set envs info* new """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          ENV INFO1 free
          ENV INFO2 back
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("Env:\n%s", data[0]["Config"].get("Env"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x SET ENVS INFO% new -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertIn("INFO1=free", dat1[0]["Config"].get("Env"))
        self.assertIn("INFO2=back", dat1[0]["Config"].get("Env"))
        self.assertIn("INFO1=new", dat2[0]["Config"].get("Env"))
        self.assertIn("INFO2=new", dat2[0]["Config"].get("Env"))
        self.rm_testdir()
        self.save(testname)
    def test_938_remove_other_env(self) -> None:
        if self.no_podman(): self.skipTest(self.no_podman())
        self.test_930_remove_other_env(_podman)
    def test_930_remove_other_env(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove env other """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          ENV INFO free
          ENV OTHER text
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("Env:\n%s", data[0]["Config"].get("Env"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x REMOVE ENV OTHER -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertIn("INFO=free", dat1[0]["Config"].get("Env"))
        self.assertNotIn("OTHER=text", dat2[0]["Config"].get("Env"))
        self.rm_testdir()
        self.save(testname)
    def test_931_remove_info_envs(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into image2 remove envs info% """
        img = IMG
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          ENV INFO1 free
          ENV OTHER text
          ENV INFO2 next
          ENV MORE  info
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("Env:\n%s", data[0]["Config"].get("Env"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {img}:{testname}x REMOVE ENVS INFO% -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertIn("INFO1=free", dat1[0]["Config"].get("Env"))
        self.assertIn("INFO2=next", dat1[0]["Config"].get("Env"))
        self.assertNotIn("INFO1=free", dat2[0]["Config"].get("Env"))
        self.assertNotIn("INFO2=next", dat2[0]["Config"].get("Env"))
        self.assertIn("OTHER=text", dat1[0]["Config"].get("Env"))
        self.assertIn("OTHER=text", dat2[0]["Config"].get("Env"))
        self.assertIn("MORE=info", dat1[0]["Config"].get("Env"))
        self.rm_testdir()
        self.save(testname)
    def test_990_check_remote_repository(self, docker: Optional[str] = None) -> None:
        """ docker-copyedit.py from image1 into remote-repo:image2 remove envs info% """
        img = IMG
        remote_img = "nonlocal.registry.example.com:5000/docker-copyedit"
        python = _python
        docker = docker or _docker
        copyedit = _copyedit(docker)
        centos = _centos()
        logg.info(": %s : %s", python, img)
        testname = self.testname()
        testdir = self.testdir()
        text_file(os_path(testdir, "Dockerfile"), F"""
          FROM {centos}
          RUN {{ echo "#! /bin/sh"; echo "exec sleep 4"; }} > /entrypoint.sh
          RUN chmod 0700 /entrypoint.sh
          ENV INFO1 free
          ENV INFO2 next
          CMD ["/entrypoint.sh"]
        """)
        cmd = F"{docker} build {testdir} -t {img}:{testname}"
        run = sh(cmd)
        logg.info("%s\n%s", run.stdout, run.stderr)
        #
        cmd = F"{docker} inspect {img}:{testname}"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.info("Env:\n%s", data[0]["Config"].get("Env"))
        dat1 = data
        #
        cmd = F"{python} {copyedit} FROM {img}:{testname} INTO {remote_img}:{testname}x REMOVE ENVS INFO% -vv"
        run = sh(cmd)
        logg.info("%s\n%s\n%s", cmd, run.stdout, run.stderr)
        err = run.stderr
        #
        cmd = F"{docker} inspect {remote_img}:{testname}x"
        run = sh(cmd)
        data = json.loads(run.stdout)
        logg.debug("CONFIG:\n%s", data[0]["Config"])
        dat2 = data
        #
        cmd = F"{docker} rmi {img}:{testname} {remote_img}:{testname}x"
        rmi = sh(cmd)
        logg.info("[%s] %s", rmi.returncode, cmd)
        #
        self.assertIn("INFO1=free", dat1[0]["Config"].get("Env"))
        self.assertIn("INFO2=next", dat1[0]["Config"].get("Env"))
        self.assertNotIn("INFO1=free", dat2[0]["Config"].get("Env"))
        self.assertNotIn("INFO2=next", dat2[0]["Config"].get("Env"))
        self.assertIn("image is not local", err)
        self.rm_testdir()
        self.save(testname)
    def test_999_coverage(self) -> None:
        python = _python
        if _coverage:
            files = glob.glob(os.path.join(TMP, ".coverage.*"))
            logg.info("showing coverage for %s tests", len(files))
            cmd = F"{python} -m coverage combine {TMP}"
            sh(cmd)
            cmd = F"{python} -m coverage annotate"
            run = sh(cmd)
            logg.info("%s", run.stdout)
            cmd = F"{python} -m coverage report"
            run = sh(cmd)
            logg.info("%s", run.stdout)
            cmd = F"{python} -m coverage xml -o " + _coverage_file
            run = sh(cmd)
            logg.info("%s %s", _coverage_file, run.stdout)
        logg.warning("coverage %s", _coverage)
        # self.skipTest("coverage result")

if __name__ == "__main__":
    ## logging.basicConfig(level = logging.INFO)
    # unittest.main()
    from optparse import OptionParser # pylint: disable=deprecated-module
    cmdline = OptionParser("%prog [options] test*")
    cmdline.add_option("-v", "--verbose", action="count", default=0,
                       help="less verbose logging [%default]")
    cmdline.add_option("-^", "--quiet", action="count",
                       default=0, help="less verbose logging")
    cmdline.add_option("-k", "--keep", action="count",
                       default=0, help="keep testdir = ./tmp/{testname}/")
    cmdline.add_option("-p", "--python", metavar="EXE", default=_python,
                       help="use another python interpreter [%default]")
    cmdline.add_option("-D", "--docker", metavar="EXE", default=_docker,
                       help="use another docker container tool [%default]")
    cmdline.add_option("-P", "--podman", metavar="EXE", default=_podman,
                       help="run tests with alternative tool [%default]")
    cmdline.add_option("-S", "--script", metavar="EXE", default=_script,
                       help="use another script to be tested [%default]")
    cmdline.add_option("-f", "--force", action="count", default=0,
                       help="do not skip some tests [%default]")
    cmdline.add_option("--image", metavar="NAME", default=_image,
                       help="centos base image [%default]")
    cmdline.add_option("--coverage", action="store_true", default=_coverage,
                       help="run with coverage [%default]")
    cmdline.add_option("--failfast", action="store_true", default=False,
                       help="Stop the test run on the first error or failure")
    cmdline.add_option("--xmlresults", metavar="FILE", default=None,
                       help="capture results as a junit xml file [%default]")
    opt, args = cmdline.parse_args()
    logging.basicConfig(level=logging.WARNING - opt.verbose * 5 + 10 * opt.quiet)
    _python = opt.python
    _docker = opt.docker
    _podman = opt.podman
    _script = opt.script
    _force = int(opt.force)
    _keep = int(opt.keep)
    _image = opt.image
    _coverage = opt.coverage
    #
    suite = unittest.TestSuite()
    if not args: args = ["test_*"]
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
        import xmlrunner  # type: ignore[import,import-error,unused-ignore]
        Runner = xmlrunner.XMLTestRunner
        result = Runner(xmlresults).run(suite)
    else:
        Runner = unittest.TextTestRunner
        result = Runner(verbosity=opt.verbose, failfast=opt.failfast).run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
