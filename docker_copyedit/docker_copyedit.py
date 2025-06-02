#! /usr/bin/env python3
# pylint: disable=missing-class-docstring,missing-function-docstring,line-too-long,too-many-lines,too-many-nested-blocks,superfluous-parens
# pylint: disable=consider-using-f-string,consider-using-enumerate,consider-iterating-dictionary
# pylint: disable=multiple-statements,invalid-name,unspecified-encoding,undefined-loop-variable,global-statement
# pylint: disable=consider-using-with,too-many-branches,too-many-statements,too-many-locals,no-else-continue,no-else-return,no-else-raise
""" 
edit docker image metadata (including remove docker volume settings)         /
use --docker=podman to switch the images list to work on.                    /
try docker-copyedit.py FROM image1 INTO image2 REMOVE ALL VOLUMES"""
__copyright__ = "(C) 2017-2025 Guido U. Draheim, licensed under the EUPL"
__version__ = "1.5.1221"

from typing import Optional, NamedTuple, Union, Tuple, Iterator, List, Dict, Sequence
import subprocess
import sys
import os
import re
import json
import shutil
import hashlib
import datetime
import logging
from fnmatch import fnmatchcase as fnmatch

logg = logging.getLogger("edit")

MAX_PATH = 1024  # on Win32 = 260 / Linux PATH_MAX = 4096 / Mac = 1024
MAX_NAME = 253
MAX_PART = 63
MAX_VERSION = 127
MAX_COLLISIONS = 100

TMPDIR = "load.tmp"
DOCKER = "docker"  # override --docker=podman to use it for FROM image1 INTO image2
PODMAN = "podman"  # use PODMAN image1 INTO image2 to work only on podman images
IMPORT = ""  # use FROM image1 IMPORT image2 to move an image from docker to podman
TAR = "tar"
KEEPDIR = 0
KEEPDATADIR = False
KEEPSAVEFILE = False
KEEPINPUTFILE = False
KEEPOUTPUTFILE = False
DRYRUN = False
OK = True
NULL = "NULL"

StringConfigs = {"user": "User", "domainname": "Domainname",
                 "workingdir": "WorkingDir", "workdir": "WorkingDir", "hostname": "Hostname"}
StringMeta = {"author": "author", "os": "os", "architecture": "architecture", "arch": "architecture", "variant": "variant"}
StringCmd = {"cmd": "Cmd", "entrypoint": "Entrypoint"}


def decodes(text: Union[str, bytes]) -> str:
    if isinstance(text, bytes):
        encoded = sys.getdefaultencoding()
        if encoded in ["ascii"]:
            encoded = "utf-8"
        try:
            return text.decode(encoded)
        except UnicodeDecodeError:
            return text.decode("latin-1")
    return text

class ShellResult(NamedTuple):
    returncode: int
    stdout: str
    stderr: str

class ShellException(Exception):
    def __init__(self, msg: str, result: ShellResult) -> None:
        Exception.__init__(self, msg)
        self.result = result

def sh(cmd: str = ":", shell: bool =True, check: bool=True, ok: Optional[bool]=None, default: str="") -> ShellResult:
    if ok is None:
        ok = not DRYRUN
    if not ok:
        logg.info("skip %s", cmd)
        return ShellResult(0, default, "")
    # pylint: disable=redefined-outer-name
    run = subprocess.Popen(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    run.wait()
    assert run.stdout is not None and run.stderr is not None
    result = ShellResult(run.returncode, decodes(run.stdout.read()), decodes(run.stderr.read()))
    if check and result.returncode:
        logg.error("CMD %s", cmd)
        logg.error("EXIT %s", result.returncode)
        logg.error("STDOUT %s", result.stdout)
        logg.error("STDERR %s", result.stderr)
        raise ShellException("shell command failed", result)
    return result

def portprot(arg: str) -> Tuple[str, str]:
    port, prot = arg, ""
    if "/" in arg:
        port, prot = arg.rsplit("/", 1)
    if port and port[0] in "0123456789":
        pass
    else:
        import socket # pylint: disable=import-outside-toplevel
        if prot:
            portnum = socket.getservbyname(port, prot)
        else:
            portnum = socket.getservbyname(port)
        port = str(portnum)
    if not prot:
        prot = "tcp"
    return port, prot

def need_to_remove_old_manifest() -> bool:
    return "podman" in DOCKER
def need_to_clean_whitespaces() -> bool:
    return "podman" in DOCKER
def need_to_chmod_file_stat() -> bool:
    return "podman" in DOCKER
def clean_whitespaces(text: str) -> str:
    if need_to_clean_whitespaces():
        return text.replace('": ', '":').replace(', "', ',"').replace(', {', ',{')
    return text
def chmod_file_stat(filename: str) -> None:
    if need_to_chmod_file_stat():
        os.chmod(filename, 0o644)
        os.utime(filename, (0, 0))

class ImageName:
    registry: Optional[str]
    image: str
    version: Optional[str]
    def __init__(self, image: str) -> None:
        self.registry = None
        self.image = image
        self.version = None
        self.parse(image)
    def parse(self, image: str) -> None:
        parsing = image
        parts = image.split("/")
        if ":" in parts[-1] or "@" in parts[-1]:
            colon = parts[-1].find(":")
            atref = parts[-1].find("@")
            if colon >= 0 and atref >= 0:
                first = min(colon, atref)
            else:
                first = max(colon, atref)
            version = parts[-1][first:]
            parts[-1] = parts[-1][:first]
            self.version = version
            self.image = "/".join(parts)
        if len(parts) > 1 and ":" in parts[0]:
            registry = parts[0]
            parts = parts[1:]
            self.registry = registry
            self.image = "/".join(parts)
        logg.debug("image parsing = %s", parsing)
        logg.debug(".registry = %s", self.registry)
        logg.debug(".image = %s", self.image)
        logg.debug(".version = %s", self.version)
    def __str__(self) -> str:
        image = self.image
        if self.registry:
            image = "/".join([self.registry, image])
        if self.version:
            image += self.version
        return image
    def tag(self) -> str:
        image = self.image
        if self.registry:
            image = "/".join([self.registry, image])
        if self.version:
            image += self.version
        else:
            image += ":latest"
        return image
    def local(self) -> bool:
        if not self.registry: return True
        if "." not in self.registry: return True
        if "localhost" in self.registry: return True
        return False
    def valid(self) -> bool:
        return not list(self.problems())
    def problems(self) -> Iterator[str]:
        # https://docs.docker.com/engine/reference/commandline/tag/
        # https://github.com/docker/distribution/blob/master/reference/regexp.go
        if self.registry and self.registry.startswith("["):
            if len(self.registry) > MAX_NAME:
                yield "registry name: full name may not be longer than %i characters" % MAX_NAME
                yield "registry name= " + self.registry
            x = self.registry.find("]")
            if not x:
                yield "registry name: invalid ipv6 number (missing bracket)"
                yield "registry name= " + self.registry
            port = self.registry[x + 1:]
            if port:
                m = re.match("^:[A-Za-z0-9]+$", port)
                if not m:
                    yield 'registry name: invalid ipv6 port (only alnum)'
                    yield "registry name= " + port
            base = self.registry[:x]
            if not base:
                yield "registry name: invalid ipv6 number (empty)"
            else:
                m = re.match("^[0-9abcdefABCDEF:]*$", base)
                if not m:
                    yield "registry name: invalid ipv6 number (only hexnum+colon)"
                    yield "registry name= " + base
        elif self.registry:
            if len(self.registry) > MAX_NAME:
                yield "registry name: full name may not be longer than %i characters" % MAX_NAME
                yield "registry name= " + self.registry
            registry = self.registry
            if registry.count(":") > 1:
                yield "a colon may only be used to designate the port number"
                yield "registry name= " + registry
            elif registry.count(":") == 1:
                registry, port = registry.split(":", 1)
                m = re.match("^[A-Za-z0-9]+$", port)
                if not m:
                    yield 'registry name: invalid ipv4 port (only alnum)'
                    yield "registry name= " + registry
            parts = registry.split(".")
            if "" in parts:
                yield "no double dots '..' allowed in registry names"
                yield "registry name= " + registry
            for part in parts:
                if len(part) > MAX_PART:
                    yield "registry name: dot-separated parts may only have %i characters" % MAX_PART
                    yield "registry name= " + part
                m = re.match("^[A-Za-z0-9-]*$", part)
                if not m:
                    yield "registry name: dns names may only have alnum+dots+dash"
                    yield "registry name= " + part
                if part.startswith("-"):
                    yield "registry name: dns name parts may not start with a dash"
                    yield "registry name= " + part
                if part.endswith("-") and len(part) > 1:
                    yield "registry name: dns name parts may not end with a dash"
                    yield "registry name= " + part
        if self.image:
            if len(self.image) > MAX_NAME:
                yield "image name: should not be longer than %i characters (min path_max)" % MAX_NAME
                yield "image name= " + self.image
            if len(self.image) > MAX_PATH:
                yield "image name: can not be longer than %i characters (limit path_max)" % MAX_PATH
                yield "image name= " + self.image
            parts = self.image.split("/")
            for part in parts:
                if not part:
                    yield "image name: double slashes are not a good idea"
                    yield "image name= " + part
                    continue
                if len(part) > MAX_NAME:
                    yield "image name: slash-separated parts should only have %i characters" % MAX_NAME
                    yield "image name= " + part
                separators = "._-"
                m = re.match("^[a-z0-9._-]*$", part)
                if not m:
                    yield "image name: only lowercase+digits+dots+dash+underscore"
                    yield "image name= " + part
                if part[0] in separators:
                    yield "image name: components may not start with a separator (%s)" % part[0]
                    yield "image name= " + part
                if part[-1] in separators and len(part) > 1:
                    yield "image name: components may not end with a separator (%s)" % part[-1]
                    yield "image name= " + part
                elems = part.split(".")
                if "" in elems:
                    yield "image name: only single dots are allowed, not even double"
                    yield "image name= " + part
                elems = part.split("_")
                if len(elems) > 2:
                    for x in range(len(elems) - 1):
                        if not elems[x] and not elems[x + 1]:
                            yield "image name: only single or double underscores are allowed"
                            yield "image name= " + part
        if self.version:
            if len(self.version) > MAX_VERSION:
                yield "image version: may not be longer than %i characters" % MAX_VERSION
                yield "image version= " + self.version
            if self.version[0] not in ":@":
                yield "image version: must either be :version or @digest"
                yield "image version= " + self.version
            if len(self.version) > 1 and self.version[1] in "-.":
                yield "image version: may not start with dots or dash"
                yield "image version= " + self.version
            version = self.version[1:]
            if not version:
                yield "image version: no name provided after '%s'" % self.version[0]
                yield "image version= " + self.version
            m = re.match("^[A-Za-z0-9_.-]*$", version)
            if not m:
                yield 'image version: only alnum+undescore+dots+dash are allowed'
                yield "image version= " + self.version

Commands = List[Tuple[Optional[str], Optional[str], Optional[str]]]
def edit_image(inp: Optional[str], out: Optional[str], edits: Commands) -> int:
    if not inp:
        raise CommandError("no FROM value provided")
    elif not out:
        raise CommandError("no INTO value provided")
    else:
        inp_name = ImageName(inp)
        out_name = ImageName(out)
        for problem in inp_name.problems():
            logg.warning("FROM value: %s", problem)
        for problem in out_name.problems():
            logg.warning("INTO value: %s", problem)
        if not out_name.local():
            logg.warning("output image is not local for the 'docker load' step")
        else:
            logg.warning("output image is local (%s)", out_name.registry)
        inp_tag = inp
        out_tag = out_name.tag()
        #
        tmpdir = TMPDIR
        if not os.path.isdir(tmpdir):
            logg.debug("mkdir %s", tmpdir)
            if not DRYRUN:
                os.makedirs(tmpdir)
        datadir = os.path.join(tmpdir, "data")
        if not os.path.isdir(datadir):
            logg.debug("mkdir %s", datadir)
            if not DRYRUN:
                os.makedirs(datadir)
        inputfile = os.path.join(tmpdir, "saved.tar")
        outputfile = os.path.join(tmpdir, "ready.tar")
        inputfile_hints = ""
        outputfile_hints = ""
        #
        docker = DOCKER
        tar = TAR
        if KEEPSAVEFILE:
            if os.path.exists(inputfile):
                os.remove(inputfile)
            sh(F"{docker} save {inp} -o {inputfile}")
            sh(F"{tar} xf {inputfile} -C {datadir}")
            logg.info("%s", F"new {datadir} from {inputfile}")
        else:
            sh(F"{docker} save {inp} | {tar} x -f - -C {datadir}")
            logg.info("%s", F"new {datadir} from {docker} save")
            inputfile_hints += " (not created)"
        tmplist = sh(F"ls -l {tmpdir}")
        logg.debug(tmplist.stdout)
        #
        if not DRYRUN:
            changed = edit_datadir(datadir, out_tag, edits)
            if changed or IMPORT:
                outfile = os.path.realpath(outputfile)
                sh(F"cd {datadir} && {tar} cf {outfile} .")
                import_docker = IMPORT or DOCKER
                sh(F"{import_docker} load -i {outputfile}")
                logg.debug("done loading %s", outputfile)
            else:
                logg.warning("unchanged image from %s", inp_tag)
                outputfile_hints += " (not created)"
                if inp != out:
                    sh(F"{docker} tag {inp_tag} {out_tag}")
                    logg.warning(" tagged old image as %s", out_tag)
        #
        if KEEPDATADIR:
            logg.warning("keeping %s", datadir)
        else:
            if os.path.exists(datadir):
                shutil.rmtree(datadir)
        if KEEPINPUTFILE:
            logg.warning("keeping %s%s", inputfile, inputfile_hints)
        else:
            if os.path.exists(inputfile):
                os.remove(inputfile)
        if KEEPOUTPUTFILE:
            logg.warning("keeping %s%s", outputfile, outputfile_hints)
        else:
            if os.path.exists(outputfile):
                os.remove(outputfile)
        return os.EX_OK


def edit_datadir(datadir: str, out: Optional[str], edits: Commands) -> int:
    if OK:
        manifest_file = "manifest.json"
        manifest_filename = os.path.join(datadir, manifest_file)
        with open(manifest_filename) as _manifest_file:
            manifest = json.load(_manifest_file)
        replaced: Dict[str, Optional[str]] = {}
        for item in range(len(manifest)):
            config_file = manifest[item]["Config"]
            config_filename = os.path.join(datadir, config_file)
            replaced[config_filename] = None
        #
        args: List[str]
        for item in range(len(manifest)):
            config_file = manifest[item]["Config"]
            config_filename = os.path.join(datadir, config_file)
            with open(config_filename) as _config_file:
                config = json.load(_config_file)
            old_config_text = clean_whitespaces(json.dumps(config))  # to compare later
            #
            for CONFIG in ['config', 'Config', 'container_config']:
                if CONFIG not in config:
                    logg.debug("no section '%s' in config", CONFIG)
                    continue
                logg.debug("with %s: %s", CONFIG, config[CONFIG])
                for action, target, arg in edits:
                    if action in ["remove", "rm"] and target in ["volume", "volumes"]:
                        key = 'Volumes'
                        if not arg:
                            logg.error("can not do edit %s %s without arg: <%s>", action, target, arg)
                            continue
                        elif target in ["volumes"] and arg in ["*", "%"]:
                            args = []
                            try:
                                if key in config[CONFIG] and config[CONFIG][key] is not None:
                                    del config[CONFIG][key]
                                    logg.warning("done actual config %s %s '%s'", action, target, arg)
                            except KeyError:
                                logg.warning("there was no '%s' in %s", key, config_filename)
                        elif target in ["volumes"]:
                            pattern = arg.replace("%", "*")
                            args = []
                            if key in config[CONFIG] and config[CONFIG][key] is not None:
                                for entry in config[CONFIG][key]:
                                    if fnmatch(entry, pattern):
                                        args += [entry]
                            logg.debug("volume pattern %s -> %s", pattern, args)
                            if not args:
                                logg.warning("%s pattern '%s' did not match anything", target, pattern)
                        elif arg.startswith("/"):
                            args = [arg]
                        else:
                            logg.error("can not do edit %s %s %s", action, target, arg)
                            continue
                        #
                        for arg in args:
                            entry = os.path.normpath(arg)
                            try:
                                if config[CONFIG][key] is None:
                                    raise KeyError("null section " + key)
                                del config[CONFIG][key][entry]
                            except KeyError:
                                logg.warning("there was no '%s' in '%s' of  %s", entry, key, config_filename)
                    if action in ["remove", "rm"] and target in ["port", "ports"]:
                        key = 'ExposedPorts'
                        if not arg:
                            logg.error("can not do edit %s %s without arg: <%s>", action, target, arg)
                            continue
                        elif target in ["ports"] and arg in ["*", "%"]:
                            args = []
                            try:
                                if key in config[CONFIG] and config[CONFIG][key] is not None:
                                    del config[CONFIG][key]
                                    logg.warning("done actual config %s %s %s", action, target, arg)
                            except KeyError:
                                logg.warning("there were no '%s' in %s", key, config_filename)
                        elif target in ["ports"]:
                            pattern = arg.replace("%", "*")
                            args = []
                            if key in config[CONFIG] and config[CONFIG][key] is not None:
                                for entry in config[CONFIG][key]:
                                    if fnmatch(entry, pattern):
                                        args += [entry]
                            logg.debug("ports pattern %s -> %s", pattern, args)
                            if not args:
                                logg.warning("%s pattern '%s' did not match anything", target, pattern)
                        else:
                            args = [arg]
                        #
                        for arg in args:
                            port, prot = portprot(arg)
                            if not port:
                                logg.error("can not do edit %s %s %s", action, target, arg)
                                return 64  # EX_USAGE
                            entry = F"{port}/{prot}"
                            try:
                                if config[CONFIG][key] is None:
                                    raise KeyError("null section " + key)
                                del config[CONFIG][key][entry]
                                logg.info("done rm-port '%s' from '%s'", entry, key)
                            except KeyError:
                                logg.warning("there was no '%s' in '%s' of  %s", entry, key, config_filename)
                    if action in ["append", "add"] and target in ["volume"]:
                        if not arg:
                            logg.error("can not do edit %s %s without arg: <%s>", action, target, arg)
                            continue
                        key = 'Volumes'
                        entry = os.path.normpath(arg)
                        if config[CONFIG].get(key) is None:
                            config[CONFIG][key] = {}
                        if arg not in config[CONFIG][key]:
                            config[CONFIG][key][entry] = {}
                            logg.info("added %s to %s", entry, key)
                    if action in ["append", "add"] and target in ["port"]:
                        if not arg:
                            logg.error("can not do edit %s %s without arg: <%s>", action, target, arg)
                            continue
                        key = 'ExposedPorts'
                        port, prot = portprot(arg)
                        entry = "%s/%s" % (port, prot)
                        if key not in config[CONFIG]:
                            config[CONFIG][key] = {}
                        if arg not in config[CONFIG][key]:
                            config[CONFIG][key][entry] = {}
                            logg.info("added %s to %s", entry, key)
                    if action in ["set", "set-shell"] and target in ["entrypoint"]:
                        key = 'Entrypoint'
                        try:
                            if not arg:
                                running = None
                            elif action in ["set-shell"]:
                                running = ["/bin/sh", "-c", arg]
                            elif arg.startswith("["):
                                running = json.loads(arg)
                            else:
                                running = [arg]
                            config[CONFIG][key] = running
                            logg.warning("done edit %s %s", action, arg)
                        except KeyError:
                            logg.warning("there was no '%s' in %s", key, config_filename)
                    if action in ["set", "set-shell"] and target in ["cmd"]:
                        key = 'Cmd'
                        try:
                            if not arg:
                                running = None
                            elif action in ["set-shell"]:
                                running = ["/bin/sh", "-c", arg]
                                logg.info("%s %s", action, running)
                            elif arg.startswith("["):
                                running = json.loads(arg)
                            else:
                                running = [arg]
                            config[CONFIG][key] = running
                            logg.warning("done edit %s %s", action, arg)
                        except KeyError:
                            logg.warning("there was no '%s' in %s", key, config_filename)
                    if action in ["set"] and target in StringConfigs:
                        key = StringConfigs[target]
                        try:
                            if not arg:
                                value = ''
                            else:
                                value = arg
                            if key in config[CONFIG]:
                                if config[CONFIG][key] == value:
                                    logg.warning("unchanged config '%s' %s", key, value)
                                else:
                                    config[CONFIG][key] = value
                                    logg.warning("done edit config '%s' %s", key, value)
                            else:
                                config[CONFIG][key] = value
                                logg.warning("done  new config '%s' %s", key, value)
                        except KeyError:
                            logg.warning("there was no config %s in %s", target, config_filename)
                    if action in ["set"] and target in StringMeta:
                        key = StringMeta[target]
                        try:
                            if not arg:
                                value = ''
                            else:
                                value = arg
                            if key in config:
                                if config[key] == value:
                                    logg.warning("unchanged meta '%s' %s", key, value)
                                else:
                                    config[key] = value
                                    logg.warning("done edit meta '%s' %s", key, value)
                            else:
                                config[key] = value
                                logg.warning("done  new meta '%s' %s", key, value)
                        except KeyError:
                            logg.warning("there was no meta %s in %s", target, config_filename)
                    if action in ["set-label"]:
                        key = "Labels"
                        try:
                            value = arg or ''
                            if key not in config[CONFIG]:
                                config[CONFIG][key] = {}
                            if target in config[CONFIG][key]:
                                if config[CONFIG][key][target] == value:
                                    logg.warning("unchanged label '%s' %s", target, value)
                                else:
                                    config[CONFIG][key][target] = value
                                    logg.warning("done edit label '%s' %s", target, value)
                            else:
                                config[CONFIG][key][target] = value
                                logg.warning("done  new label '%s' %s", target, value)
                        except KeyError:
                            logg.warning("there was no config %s in %s", target, config_filename)
                    if action in ["remove-label", "rm-label"]:
                        if not target:
                            logg.error("can not do edit %s without arg: <%s>", action, target)
                            continue
                        key = "Labels"
                        try:
                            if key in config[CONFIG]:
                                if config[CONFIG][key] is None:
                                    raise KeyError("null section " + key)
                                del config[CONFIG][key][target]
                                logg.warning("done actual %s %s ", action, target)
                        except KeyError:
                            logg.warning("there was no label %s in %s", target, config_filename)
                    if action in ["remove-labels", "rm-labels"]:
                        if not target:
                            logg.error("can not do edit %s without arg: <%s>", action, target)
                            continue
                        key = "Labels"
                        try:
                            pattern = target.replace("%", "*")
                            args = []
                            if key in config[CONFIG] and config[CONFIG][key] is not None:
                                for entry in config[CONFIG][key]:
                                    if fnmatch(entry, pattern):
                                        args += [entry]
                            for arg in args:
                                del config[CONFIG][key][arg]
                                logg.warning("done actual %s %s (%s)", action, target, arg)
                        except KeyError:
                            logg.warning("there was no label %s in %s", target, config_filename)
                    if action in ["remove-envs", "rm-envs"]:
                        if not target:
                            logg.error("can not do edit %s without arg: <%s>", action, target)
                            continue
                        key = "Env"
                        try:
                            pattern = target.strip() + "=*"
                            pattern = pattern.replace("%", "*")
                            found = []
                            if key in config[CONFIG] and config[CONFIG][key] is not None:
                                for n, entry in enumerate(config[CONFIG][key]):
                                    if fnmatch(entry, pattern):
                                        found += [n]
                            for n in reversed(found):
                                del config[CONFIG][key][n]
                                logg.warning("done actual %s %s (%s)", action, target, n)
                        except KeyError:
                            logg.warning("there was no label %s in %s", target, config_filename)
                    if action in ["remove-env", "rm-env"]:
                        if not target:
                            logg.error("can not do edit %s without arg: <%s>", action, target)
                            continue
                        key = "Env"
                        try:
                            if "=" in target:
                                pattern = target.strip()
                            else:
                                pattern = target.strip() + "=*"
                            found = []
                            if key in config[CONFIG] and config[CONFIG][key] is not None:
                                for n, entry in enumerate(config[CONFIG][key]):
                                    if fnmatch(entry, pattern):
                                        found += [n]
                            for n in reversed(found):
                                del config[CONFIG][key][n]
                                logg.warning("done actual %s %s (%s)", action, target, n)
                        except KeyError:
                            logg.warning("there was no label %s in %s", target, config_filename)
                    if action in ["remove-healthcheck", "rm-healthcheck"]:
                        key = "Healthcheck"
                        try:
                            del config[CONFIG][key]
                            logg.warning("done actual %s %s", action, target)
                        except KeyError:
                            logg.warning("there was no %s in %s", key, config_filename)
                    if action in ["set-envs"]:
                        if not target:
                            logg.error("can not do edit %s without arg: <%s>", action, target)
                            continue
                        key = "Env"
                        try:
                            if "=" in target:
                                pattern = target.strip().replace("%", "*")
                            else:
                                pattern = target.strip().replace("%", "*") + "=*"
                            if key not in config[CONFIG]:
                                config[key] = {}
                            found = []
                            for n, entry in enumerate(config[CONFIG][key]):
                                if fnmatch(entry, pattern):
                                    found += [n]
                            if found:
                                for n in reversed(found):
                                    oldvalue = config[CONFIG][key][n]
                                    varname = oldvalue.split("=", 1)[0]
                                    newvalue = varname + "=" + (arg or '')
                                    if config[CONFIG][key][n] == newvalue:
                                        logg.warning("unchanged var '%s' %s", target, newvalue)
                                    else:
                                        config[CONFIG][key][n] = newvalue
                                        logg.warning("done edit var '%s' %s", target, newvalue)
                            elif "=" in target or "*" in target or "%" in target or "?" in target or "[" in target:
                                logg.info("non-existing var pattern '%s'", target)
                            else:
                                value = target.strip() + "=" + (arg or '')
                                config[CONFIG][key] += [pattern + value]
                                logg.warning("done  new var '%s' %s", target, value)
                        except KeyError:
                            logg.warning("there was no config %s in %s", target, config_filename)
                    if action in ["set-env"]:
                        if not target:
                            logg.error("can not do edit %s without arg: <%s>", action, target)
                            continue
                        key = "Env"
                        try:
                            pattern = target.strip() + "="
                            if key not in config[CONFIG]:
                                config[key] = {}
                            found = []
                            for n, entry in enumerate(config[CONFIG][key]):
                                if entry.startswith(pattern):
                                    found += [n]
                            if found:
                                for n in reversed(found):
                                    oldvalue = config[CONFIG][key][n]
                                    varname = oldvalue.split("=", 1)[0]
                                    newvalue = varname + "=" + (arg or '')
                                    if config[CONFIG][key][n] == newvalue:
                                        logg.warning("unchanged var '%s' %s", target, newvalue)
                                    else:
                                        config[CONFIG][key][n] = newvalue
                                        logg.warning("done edit var '%s' %s", target, newvalue)
                            elif "=" in target or "*" in target or "%" in target or "?" in target or "[" in target:
                                logg.info("may not use pattern characters in env variable '%s'", target)
                            else:
                                value = target.strip() + "=" + (arg or '')
                                config[CONFIG][key] += [pattern + value]
                                logg.warning("done  new var '%s' %s", target, value)
                        except KeyError:
                            logg.warning("there was no config %s in %s", target, config_filename)
                logg.debug("done %s: %s", CONFIG, config[CONFIG])
            new_config_text = clean_whitespaces(json.dumps(config))
            if new_config_text != old_config_text:
                for CONFIG in ['history']:
                    if CONFIG in config:
                        myself = os.path.basename(sys.argv[0])
                        config[CONFIG] += [{"empty_layer": True,
                                            "created_by": "%s #(%s)" % (myself, __version__),
                                            "created": datetime.datetime.utcnow().isoformat() + "Z"}]
                        new_config_text = clean_whitespaces(json.dumps(config))
                new_config_md = hashlib.sha256()
                new_config_md.update(new_config_text.encode("utf-8"))
                for collision in range(1, MAX_COLLISIONS):
                    new_config_hash = new_config_md.hexdigest()
                    new_config_file = "%s.json" % new_config_hash
                    new_config_filename = os.path.join(datadir, new_config_file)
                    if new_config_filename in replaced.keys() or new_config_filename in replaced.values():
                        logg.info("collision %s %s", collision, new_config_filename)
                        new_config_md.update(" ".encode("utf-8"))
                        continue
                    break
                with open(new_config_filename, "wb") as fp:
                    fp.write(new_config_text.encode("utf-8"))
                logg.info("written new %s", new_config_filename)
                logg.info("removed old %s", config_filename)
                chmod_file_stat(new_config_filename)
                #
                manifest[item]["Config"] = new_config_file
                replaced[config_filename] = new_config_filename
            else:
                logg.info("  unchanged %s", config_filename)
            if "RepoTags" in manifest[item]:
                manifest[item]["RepoTags"] = [out]
        manifest_text = clean_whitespaces(json.dumps(manifest))
        manifest_filename = os.path.join(datadir, manifest_file)
        # report the result
        with open(manifest_filename + ".tmp", "wb") as fp:
            fp.write(manifest_text.encode("utf-8"))
        if need_to_remove_old_manifest():  # podman
            if os.path.isfile(manifest_filename + ".old"):
                os.remove(manifest_filename + ".old")
            chmod_file_stat(manifest_filename)
            os.rename(manifest_filename, manifest_filename + ".old")
        os.rename(manifest_filename + ".tmp", manifest_filename)
        changed = 0
        for a, b in replaced.items():
            if b:
                changed += 1
                logg.debug("replaced\n\t old %s\n\t new %s", a, b)
            else:
                logg.debug("unchanged\n\t old %s", a)
        logg.debug("updated\n\t --> %s", manifest_filename)
        logg.debug("changed %s layer metadata", changed)
        return changed
    return 0


class CommandError(RuntimeError):
    pass
def parse_commands(args: Sequence[str]) -> Tuple[Optional[str], Optional[str], Commands]:
    global IMPORT, DOCKER # pylint: disable=global-statement
    inp = None
    out = None
    action = None
    target = None
    commands: Commands = []
    known_set_targets = list(StringCmd.keys()) + list(StringConfigs.keys()) + list(StringMeta.keys())
    for n in range(len(args)):
        arg = args[n]
        if target is not None:
            if target.lower() in ["all"]:
                # remove all ports => remove ports *
                commands.append((action, arg.lower(), "*"))
            elif action in ["set", "set-shell"] and target.lower() in ["null", "no"]:
                # set null cmd => set cmd <none>
                if arg.lower() not in known_set_targets:
                    raise CommandError("bad edit command: %s %s %s" % (action, target, arg))
                commands.append((action, arg.lower(), None))
            elif action in ["set", "set-shell"] and target.lower() in known_set_targets:
                # set cmd null => set cmd <none>
                if arg.lower() in [NULL.lower(), NULL.upper()]:
                    logg.info("do not use '%s %s %s' - use 'set null %s'", action, target, arg, target.lower())
                    commands.append((action, target.lower(), None))
                elif arg.lower() in ['']:
                    logg.error("do not use '%s %s %s' - use 'set null %s'", action, target, '""', target.lower())
                    logg.warning("we assume <null> here but that will change in the future")
                    commands.append((action, target.lower(), None))
                else:
                    commands.append((action, target.lower(), arg))
            else:
                commands.append((action, target, arg))
            action, target = None, None
            continue
        if action is None:
            if arg in ["and", "+", ",", "/"]:
                continue
            action = arg.lower()
            continue
        rm_labels = ["rm-label", "remove-label", "rm-labels", "remove-labels"]
        rm_vars = ["rm-var", "remove-var", "rm-vars", "remove-vars"]
        rm_envs = ["rm-env", "remove-env", "rm-envs", "remove-envs"]
        if action in (rm_labels + rm_vars + rm_envs):
            target = arg
            commands.append((action, target, None))
            action, target = None, None
            continue
        #
        if action in ["set"] and arg.lower() in ["shell", "label", "labels", "var", "vars", "env", "envs"]:
            action = "%s-%s" % (action, arg.lower())
            continue
        if action in ["rm", "remove"] and arg.lower() in ["label", "labels", "var", "vars", "env", "envs"]:
            action = "%s-%s" % (action, arg.lower())
            continue
        if action in ["rm", "remove"] and arg.lower() in ["healthcheck"]:
            action = "%s-%s" % (action, arg.lower())
            commands.append((action, None, None))
            action, target = None, None
            continue
        if action in ["podman"]:
            inp = arg
            action = None
            DOCKER = PODMAN
            continue
        elif action in ["from"]:
            inp = arg
            action = None
            continue
        elif action in ["into"]:
            out = arg
            action = None
            continue
        elif action in ["import"]:
            out = arg
            action = None
            IMPORT = PODMAN
            continue
        elif action in ["remove", "rm"]:
            if arg.lower() in ["volume", "port", "all", "volumes", "ports"]:
                target = arg.lower()
                continue
            raise CommandError("unknown edit command starting with %s %s" % (action, arg))
        elif action in ["append", "add"]:
            if arg.lower() in ["volume", "port"]:
                target = arg.lower()
                continue
            raise CommandError("unknown edit command starting with %s %s" % (action, arg))
        elif action in ["set", "override"]:
            if arg.lower() in known_set_targets:
                target = arg.lower()
                continue
            if arg.lower() in ["null", "no"]:
                target = arg.lower()
                continue  # handled in "all" / "no" case
            raise CommandError("unknown edit command starting with %s %s" % (action, arg))
        elif action in ["set-shell"]:
            if arg.lower() in StringCmd:
                target = arg.lower()
                continue
            raise CommandError("unknown edit command starting with %s %s" % (action, arg))
        elif action in ["set-label", "set-var", "set-env", "set-envs"]:
            target = arg
            continue
        else:
            raise CommandError("unknown edit command starting with %s" % (action,))
    if not inp:
        raise CommandError("no input image given - use 'FROM image-name'")
    if not out:
        raise CommandError("no output image given - use 'INTO image-name'")
    return inp, out, commands

def docker_tag(inp: Optional[str], out: Optional[str]) -> None:
    docker = DOCKER
    if inp and out and inp != out:
        cmd = "{docker} tag {inp} {out}"
        logg.info("%s", cmd)
        sh(F"{docker} tag {inp} {out}", check=False)

def run(*args: str) -> int:
    try:
        inp, out, commands = parse_commands(args)
    except Exception as e: # pylint: disable=broad-exception-caught
        logg.error(" %s", e)
        return os.EX_USAGE
    if not commands:
        logg.warning("nothing to do for %s", out)
        docker_tag(inp, out)
        return os.EX_OK
    else:
        if DRYRUN:
            oldlevel = logg.level
            logg.level = logging.INFO
            logg.info(" | from %s    into %s", inp, out)
            for action, target, arg in commands:
                if arg is None:
                    arg = "<null>"
                else:
                    arg = "'%s'" % arg
                logg.info(" | %s %s   %s", action, target, arg)
            logg.level = oldlevel
        return edit_image(inp, out, commands)

def main() -> int:
    global TMPDIR, DOCKER, PODMAN, TAR, KEEPDIR, DRYRUN, NULL, KEEPDATADIR, KEEPSAVEFILE, KEEPINPUTFILE, KEEPOUTPUTFILE
    from optparse import OptionParser # pylint: disable=deprecated-module,import-outside-toplevel
    cmdline = OptionParser("%prog input-image output-image [commands...]", epilog=__doc__)
    cmdline.add_option("-v", "--verbose", action="count", default=0,
                       help="increase logging level [%default]")
    cmdline.add_option("-^", "--quiet", action="count", default=0,
                       help="less logging infos")
    cmdline.add_option("-T", "--tmpdir", metavar="DIR", default=TMPDIR,
                       help="use this base temp dir %s [%default]")
    cmdline.add_option("-D", "--docker", metavar="EXE", default=DOCKER,
                       help="use another docker container tool %s [%default]")
    cmdline.add_option("-P", "--podman", metavar="EXE", default=PODMAN,
                       help="change the alternative container tool [%default]")
    cmdline.add_option("-G", "--tar", metavar="EXE", default=TAR,
                       help="use another gnu-ish tar tool %s [%default]")
    cmdline.add_option("-k", "--keepdir", action="count", default=KEEPDIR,
                       help="keep the unpacked dirs [%default]")
    cmdline.add_option("-z", "--dryrun", action="store_true", default=DRYRUN,
                       help="only run logic, do not change anything [%default]")
    cmdline.add_option("--with-null", metavar="name", default=NULL,
                       help="specify the special value for disable [%default]")
    cmdline.add_option("-c", "--config", metavar="NAME=VAL", action="append", default=[],
                       help="..override internal variables (MAX_PATH) {%default}")
    opt, cmdline_args = cmdline.parse_args()
    logging.basicConfig(level=max(0, logging.ERROR - 10 * opt.verbose + 10 * opt.quiet))
    TMPDIR = opt.tmpdir
    DOCKER = opt.docker
    PODMAN = opt.podman
    TAR = opt.tar
    KEEPDIR = opt.keepdir
    DRYRUN = opt.dryrun
    NULL = opt.with_null
    if KEEPDIR >= 1:
        KEEPDATADIR = True
    if KEEPDIR >= 2:
        KEEPSAVEFILE = True
    if KEEPDIR >= 3:
        KEEPINPUTFILE = True
    if KEEPDIR >= 4:
        KEEPOUTPUTFILE = True
    ########################################
    for setting in opt.config:
        nam, val = setting, "1"
        if "=" in setting:
            nam, val = setting.split("=", 1)
        elif nam.startswith("no-") or nam.startswith("NO-"):
            nam, val = nam[3:], "0"
        elif nam.startswith("No") or nam.startswith("NO"):
            nam, val = nam[2:], "0"
        if nam in globals():
            old = globals()[nam]
            if old is False or old is True:
                logg.debug("yes %s=%s", nam, val)
                globals()[nam] = (val in ("true", "True", "TRUE", "yes", "y", "Y", "YES", "1"))
            elif isinstance(old, float):
                logg.debug("num %s=%s", nam, val)
                globals()[nam] = float(val)
            elif isinstance(old, int):
                logg.debug("int %s=%s", nam, val)
                globals()[nam] = int(val)
            elif isinstance(old, str):
                logg.debug("str %s=%s", nam, val)
                globals()[nam] = val.strip()
            else:
                logg.warning("(ignored) unknown target type -c '%s' : %s", nam, type(old))
        else:
            logg.warning("(ignored) unknown target config -c '%s' : no such variable", nam)
    ########################################
    if len(cmdline_args) < 2:
        logg.error("not enough arguments, use --help")
        return os.EX_USAGE
    else:
        return run(*cmdline_args)

if __name__ == "__main__":
    sys.exit(main())
