#! /usr/bin/python
from __future__ import print_function

__copyright__ = "(C) 2017-2019 Guido U. Draheim, licensed under the EUPL"
__version__ = "1.3.2045"

import subprocess
import collections
import sys
import os
import re
import json
import copy
import shutil
import hashlib
import datetime
import logging
from fnmatch import fnmatchcase as fnmatch

logg = logging.getLogger("edit")

if sys.version[0] == '3':
    basestring = str
    xrange = range

TMPDIR = "load.tmp"
KEEPDIR = 0
OK=True
NULL="NULL"

StringConfigs = {"user": "User", "domainname": "Domainname", "workingdir": "WorkingDir", "workdir": "WorkingDir", "hostname": "Hostname" }
StringMeta = {"author": "author", "os": "os", "architecture": "architecture", "arch": "architecture" }
StringCmd = {"cmd": "Cmd", "entrypoint": "Entrypoint"}

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

def portprot(arg):
    port, prot = arg, ""
    if "/" in arg:
        port, prot = arg.rsplit("/", 1)
    if port and port[0] in "0123456789":
        pass
    else:
        import socket
        if prot:
            port = socket.getservbyname(port, prot)
        else:
            port = socket.getservbyname(port)
    if not prot:
        prot = "tcp"
    return port, prot

class ImageName:
    def __init__(self, image):
        self.registry = None
        self.image = image
        self.version = None
        self.parse(image)
    def parse(self, image):
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
    def __str__(self):
        image = self.image
        if self.registry:
            image = "/".join([self.registry, image])
        if self.version:
            image += self.version
        return image
    def tag(self):
        image = self.image
        if self.registry:
            image = "/".join([self.registry, image])
        if self.version:
            image += self.version
        else:
            image += ":latest"
        return image
    def valid(self):
        return not list(self.problems())
    def problems(self):
        # https://docs.docker.com/engine/reference/commandline/tag/
        # https://github.com/docker/distribution/blob/master/reference/regexp.go
        if self.registry and self.registry.startswith("["):
            if len(self.registry) > 253:
                yield "registry name: full name may not be longer than 253 characters"
                yield "registry name= " + self.registry
            x = self.registry.find("]")
            if not x:
                yield "registry name: invalid ipv6 number (missing bracket)"
                yield "registry name= " + self.registry
            port = self.registry[x+1:]
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
            if len(self.registry) > 253:
                yield "registry name: full name may not be longer than 253 characters"
                yield "registry name= " + self.registry
            registry = self.registry
            if registry.count(":") > 1:
                yield "a colon may only be used to seperate the port number"
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
                if len(part) > 63:
                    yield "registry name: dot-seperated parts may only have 63 characters"
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
            if len(self.image) > 253:
                yield "image name: should not be longer than 253 characters (min path_max)"
                yield "image name= " + self.image
            if len(self.image) > 1024:
                yield "image name: can not be longer than 1024 characters (limit path_max)"
                yield "image name= " + self.image
            parts = self.image.split("/")
            for part in parts:
                if not part:
                    yield "image name: double slashes are not a good idea"
                    yield "image name= " + part
                    continue
                if len(part) > 253:
                    yield "image name: slash-seperated parts should only have 253 characters"
                    yield "image name= " + part
                seperators = "._-"
                m = re.match("^[a-z0-9._-]*$", part)
                if not m:
                    yield "image name: only lowercase+digits+dots+dash+underscore"
                    yield "image name= " + part
                if part[0] in seperators:
                    yield "image name: components may not start with a seperator (%s)" % part[0]
                    yield "image name= " + part
                if part[-1] in seperators and len(part) > 1:
                    yield "image name: components may not end with a seperator (%s)" % part[-1]
                    yield "image name= " + part
                elems = part.split(".")
                if "" in elems:
                    yield "image name: only single dots are allowed, not even double"
                    yield "image name= " + part
                elems = part.split("_")
                if len(elems) > 2:
                    for x in xrange(len(elems)-1):
                        if not elems[x] and not elems[x+1]:
                            yield "image name: only single or double underscores are allowed"
                            yield "image name= " + part
        if self.version:
            if len(self.version) > 128:
                yield "image version: may not be longer than 127 characters"
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

def edit_image(inp, out, edits):
        if not inp:
            logg.error("no FROM value provided")
            return False
        if not out:
            logg.error("no INTO value provided")
            return False
        inp_name = ImageName(inp)
        out_name = ImageName(out)
        for problem in inp_name.problems():
            logg.warning("FROM value: %s", problem)
        for problem in out_name.problems():
            logg.warning("INTO value: %s", problem)
        inp_tag = inp
        out_tag = out_name.tag()
        #
        tmpdir = TMPDIR
        if not os.path.isdir(tmpdir):
            logg.debug("mkdir %s", tmpdir)
            if OK: os.makedirs(tmpdir)
        datadir = os.path.join(tmpdir, "data")
        if not os.path.isdir(datadir):
            logg.debug("mkdir %s", datadir)
            if OK: os.makedirs(datadir)
        inputfile = os.path.join(tmpdir, "saved.tar")
        outputfile = os.path.join(tmpdir, "ready.tar")
        #
        cmd = "docker save {inp} -o {inputfile}"
        sh(cmd.format(**locals()))
        cmd = "tar xf {inputfile} -C {datadir}"
        sh(cmd.format(**locals()))
        run = sh("ls -l {tmpdir}".format(**locals()))
        logg.debug(run.stdout)
        #
        if OK: 
            changed = edit_datadir(datadir, out_tag, edits)
            if changed:
                outfile = os.path.realpath(outputfile)
                cmd = "cd {datadir} && tar cf {outfile} ."
                sh(cmd.format(**locals()))
                cmd = "docker load -i {outputfile}"
                sh(cmd.format(**locals()))
            else:
                logg.warning("unchanged image from %s", inp_tag)
                if inp != out:
                    cmd = "docker tag {inp_tag} {out_tag}"
                    sh(cmd.format(**locals()))
                    logg.warning(" tagged old image as %s", out_tag)
        #
        if KEEPDIR >= 1:
            logg.warning("keeping %s", datadir)
        else:
            if os.path.exists(datadir):
                shutil.rmtree(datadir)
        if KEEPDIR >= 2:
            logg.warning("keeping %s", inputfile)
        else:
            if os.path.exists(inputfile):
                os.remove(inputfile)
        if KEEPDIR >= 3:
            logg.warning("keeping %s", outputfile)
        else:
            if os.path.exists(outputfile):
                 os.remove(outputfile)

def edit_datadir(datadir, out, edits):
        manifest_file = "manifest.json"
        manifest_filename = os.path.join(datadir, manifest_file)
        with open(manifest_filename) as fp:
            manifest = json.load(fp)
        replaced = {}
        for item in xrange(len(manifest)):
            config_file = manifest[item]["Config"]
            config_filename = os.path.join(datadir, config_file)
            replaced[config_filename] = None
        #
        for item in xrange(len(manifest)):
            config_file = manifest[item]["Config"]
            config_filename = os.path.join(datadir, config_file)
            with open(config_filename) as fp:
                config = json.load(fp)
            old_config_text = json.dumps(config) # to compare later
            #
            for CONFIG in ['config','Config','container_config']:
                if CONFIG not in config:
                    logg.debug("no section '%s' in config", CONFIG)
                    continue
                logg.debug("with %s: %s", CONFIG, config[CONFIG])
                for action, target, arg in edits:
                    if action in ["remove", "rm"] and target in ["volume", "volumes"]:
                        key = 'Volumes'
                        if target in ["volumes"] and arg in ["*", "%"]:
                            args = []
                            try:
                                if config[CONFIG][key] is not None:
                                    del config[CONFIG][key]
                                logg.warning("done actual config %s %s '%s'", action, target, arg)
                            except KeyError as e:
                                logg.warning("there was no '%s' in %s", key, config_filename)
                        elif target in ["volumes"]:
                            pattern = arg.replace("%", "*")
                            args = []
                            if key in config[CONFIG]:
                                for entry in config[CONFIG][key]:
                                    if fnmatch(entry, pattern):
                                        args += [ entry ]
                            logg.debug("volume pattern %s -> %s", pattern, args)
                            if not args:
                                logg.warning("%s pattern '%s' did not match anything", target, pattern)
                        elif arg.startswith("/"):
                            args = [ arg ]
                        else:
                            logg.error("can not do edit %s %s %s", action, target, arg)
                            continue
                        #
                        for arg in args:
                            entry = os.path.normpath(arg)
                            try:
                                del config[CONFIG]['Volumes'][entry]
                            except KeyError as e:
                                logg.warning("there was no '%s' in '%s' of  %s", entry, key, config_filename)
                    if action in ["remove", "rm"] and target in ["port", "ports"]:
                        key = 'ExposedPorts'
                        if target in ["ports"] and arg in ["*", "%"]:
                            args = []
                            try:
                                del config[CONFIG][key]
                                logg.warning("done actual config %s %s %s", action, target, arg)
                            except KeyError as e:
                                logg.warning("there were no '%s' in %s", key, config_filename)
                        elif target in ["ports"]:
                            pattern = arg.replace("%", "*")
                            args = []
                            if key in config[CONFIG]:
                                for entry in config[CONFIG][key]:
                                    if fnmatch(entry, pattern):
                                        args += [ entry ]
                            logg.debug("ports pattern %s -> %s", pattern, args)
                            if not args:
                                logg.warning("%s pattern '%s' did not match anything", target, pattern)
                        else:
                            args = [ arg ]
                        #
                        for arg in args:
                            port, prot = portprot(arg)
                            if not port:
                                logg.error("can not do edit %s %s %s", action, target, arg)
                                return False
                            entry = u"%s/%s" % (port, prot)
                            try:
                                del config[CONFIG][key][entry]
                                logg.info("done rm-port '%s' from '%s'", entry, key)
                            except KeyError as e:
                                logg.warning("there was no '%s' in '%s' of  %s", entry, key, config_filename)
                    if action in ["append", "add"] and target in ["volume"]:
                        key = 'Volumes'
                        entry = os.path.normpath(arg)
                        if key not in config[CONFIG]:
                            config[CONFIG][key] = {}
                        if arg not in config[CONFIG][key]:
                            config[CONFIG][key][entry] = {}
                            logg.info("added %s to %s", entry, key)
                    if action in ["append", "add"] and target in ["port"]:
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
                            if arg in ["", None ]:
                                running = None
                            elif action in ["set-shell"]:
                                running = [ "/bin/sh", "-c", arg ]
                            elif arg.startswith("["):
                                running = json.loads(arg)
                            else:
                                running = [ arg ]
                            config[CONFIG][key] = running
                            logg.warning("done edit %s %s", action, arg)
                        except KeyError as e:
                            logg.warning("there was no '%s' in %s", key, config_filename)
                    if action in ["set", "set-shell"] and target in ["cmd"]:
                        key = 'Cmd'
                        try:
                            if arg in ["", None ]:
                                running = None
                            elif action in ["set-shell"]:
                                running = [ "/bin/sh", "-c", arg ]
                                logg.info("%s %s", action, running)
                            elif arg.startswith("["):
                                running = json.loads(arg)
                            else:
                                running = [ arg ]
                            config[CONFIG][key] = running
                            logg.warning("done edit %s %s", action, arg)
                        except KeyError as e:
                            logg.warning("there was no '%s' in %s", key, config_filename)
                    if action in ["set"] and target in StringConfigs:
                        key = StringConfigs[target]
                        try:
                            if arg in ["", None ]:
                                value = u''
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
                        except KeyError as e:
                            logg.warning("there was no config %s in %s", target, config_filename)
                    if action in ["set"] and target in StringMeta:
                        key = StringMeta[target]
                        try:
                            if arg in ["", None ]:
                                value = u''
                            else:
                                value = arg 
                            if key in config:
                                if config[key] == value:
                                    logg.warning("unchanged meta '%s' %s", key, value)
                                else:
                                    config[key] = value
                                    logg.warning("done edit meta '%s' %s", key, value)
                            else:
                                logg.warning("skip missing meta '%s'", key)
                                logg.warning("config = %s", config)
                        except KeyError as e:
                            logg.warning("there was no meta %s in %s", target, config_filename)
                    if action in ["set-label"]:
                        key = "Labels"
                        try:
                            value = arg or u''
                            if key not in config[CONFIG]:
                                config[key] = {}
                            if target in config[CONFIG][key]:
                                if config[CONFIG][key][target] == value:
                                    logg.warning("unchanged label '%s' %s", target, value)
                                else:
                                    config[CONFIG][key][target] = value
                                    logg.warning("done edit label '%s' %s", target, value)
                            else:
                                config[CONFIG][key][target] = value
                                logg.warning("done  new label '%s' %s", target, value)
                        except KeyError as e:
                            logg.warning("there was no config %s in %s", target, config_filename)
                    if action in ["remove-label", "rm-label"]:
                        key = "Labels"
                        try:
                            if key in config[CONFIG]:
                                del config[CONFIG][key][target]
                                logg.warning("done actual %s %s ", action, target)
                        except KeyError as e:
                            logg.warning("there was no label %s in %s", target, config_filename)
                    if action in ["remove-labels", "rm-labels"]:
                        key = "Labels"
                        try:
                            pattern = target.replace("%", "*")
                            args = []
                            if key in config[CONFIG]:
                                for entry in config[CONFIG][key]:
                                    if fnmatch(entry, pattern):
                                        args += [ entry ]
                            for arg in args:
                                del config[CONFIG][key][arg]
                                logg.warning("done actual %s %s (%s)", action, target, arg)
                        except KeyError as e:
                            logg.warning("there was no label %s in %s", target, config_filename)
                    if action in ["remove-envs", "rm-envs"]:
                        key = "Env"
                        try:
                            pattern = target.strip() + "=*"
                            pattern = pattern.replace("%", "*")
                            found = []
                            if key in config[CONFIG]:
                                for n, entry in enumerate(config[CONFIG][key]):
                                    if fnmatch(entry, pattern):
                                        found += [ n ]
                            for n in reversed(found):
                                del config[CONFIG][key][n]
                                logg.warning("done actual %s %s (%s)", action, target, n)
                        except KeyError as e:
                            logg.warning("there was no label %s in %s", target, config_filename)
                    if action in ["remove-env", "rm-env"]:
                        key = "Env"
                        try:
                            pattern = target.strip() + "="
                            found = []
                            if key in config[CONFIG]:
                                for n, entry in enumerate(config[CONFIG][key]):
                                    if entry.startswith(pattern):
                                        found += [ n ]
                            for n in reversed(found):
                                del config[CONFIG][key][n]
                                logg.warning("done actual %s %s (%s)", action, target, n)
                        except KeyError as e:
                            logg.warning("there was no label %s in %s", target, config_filename)
                    if action in ["set-env"]:
                        key = "Env"
                        try:
                            pattern = target.strip() + "="
                            value = pattern + (arg or u'')
                            if key not in config[CONFIG]:
                                config[key] = {}
                            found = None
                            for n, entry in enumerate(config[CONFIG][key]):
                                if entry.startswith(pattern):
                                    found = n
                            if found is not None:
                                if config[CONFIG][key][found] == value:
                                    logg.warning("unchanged var '%s' %s", target, value)
                                else:
                                    config[CONFIG][key][found] = value
                                    logg.warning("done edit var '%s' %s", target, value)
                            else:
                                config[CONFIG][key] += [ pattern + value ]
                                logg.warning("done  new var '%s' %s", target, value)
                        except KeyError as e:
                            logg.warning("there was no config %s in %s", target, config_filename)
                logg.debug("done %s: %s", CONFIG, config[CONFIG])
            new_config_text = json.dumps(config)
            if new_config_text != old_config_text:
                for CONFIG in ['history']:
                    if CONFIG in config:
                        myself = os.path.basename(sys.argv[0])
                        config[CONFIG] += [ {"empty_layer": True, 
                            "created_by": "%s #(%s)" % (myself, __version__), 
                            "created": datetime.datetime.utcnow().isoformat() + "Z"} ]
                        new_config_text = json.dumps(config)
                new_config_md = hashlib.sha256()
                new_config_md.update(new_config_text.encode("utf-8"))
                for collision in xrange(1, 100):
                    new_config_hash = new_config_md.hexdigest()
                    new_config_file = "%s.json" % new_config_hash
                    new_config_filename = os.path.join(datadir, new_config_file)
                    if new_config_filename in replaced.keys() or new_config_filename in replaced.values():
                        logg.info("collision %s %s", collision, new_config_filename)
                        new_config_md.update(" ")
                        continue
                    break
                with open(new_config_filename, "wb") as fp:
                    fp.write(new_config_text.encode("utf-8"))
                logg.info("written new %s", new_config_filename)
                logg.info("removed old %s", config_filename)
                #
                manifest[item]["Config"] = new_config_file
                replaced[config_filename] = new_config_filename
            else:
                logg.info("  unchanged %s", config_filename)
            #
            if manifest[item]["RepoTags"]:
                manifest[item]["RepoTags"] = [ out ]
        manifest_text = json.dumps(manifest)
        manifest_filename = os.path.join(datadir, manifest_file)
        # report the result
        with open(manifest_filename, "wb") as fp:
            fp.write(manifest_text.encode("utf-8"))
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

def parsing(args):
    inp = None
    out = None
    action = None
    target = None
    commands = []
    known_set_targets = list(StringCmd.keys()) + list(StringConfigs.keys()) + list(StringMeta.keys())
    for n in xrange(len(args)):
        arg = args[n]
        if target is not None:
            if target.lower() in [ "all" ]:
                # remove all ports => remove ports *
                commands.append((action, arg.lower(), "*"))
            elif action in ["set", "set-shell"] and target.lower() in [ "null", "no" ]:
                # set null cmd => set cmd <none>
                if arg.lower() not in known_set_targets:
                    logg.error("bad edit command: %s %s %s", action, target, arg)
                commands.append((action, arg.lower(), None))
            elif action in ["set", "set-shell"] and target.lower() in known_set_targets:
                # set cmd null => set cmd <none>
                if arg.lower() in [ NULL.lower(), NULL.upper() ]:
                    logg.info("do not use '%s %s %s' - use 'set null %s'", action, target, arg, target.lower())
                    commands.append((action, target.lower(), None))
                elif arg.lower() in [ '' ]:
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
        if action in ["from"]:
            inp = arg
            action = None
            continue
        elif action in ["into"]:
            out = arg
            action = None
            continue
        elif action in ["remove", "rm"]:
            if arg.lower() in ["volume", "port", "all", "volumes", "ports"]:
                target = arg.lower()
                continue
            logg.error("unknown edit command starting with %s %s", action, arg)
            return None, None, None
        elif action in ["append", "add"]:
            if arg.lower() in ["volume", "port"]:
                target = arg.lower()
                continue
            logg.error("unknown edit command starting with %s %s", action, arg)
            return None, None, None
        elif action in ["set", "override"]:
            if arg.lower() in known_set_targets:
                target = arg.lower()
                continue
            if arg.lower() in [ "null", "no" ]:
                target = arg.lower()
                continue # handled in "all" / "no" case
            logg.error("unknown edit command starting with %s %s", action, arg)
            return None, None, None
        elif action in ["set-shell"]:
            if arg.lower() in StringCmd:
                target = arg.lower()
                continue
            logg.error("unknown edit command starting with %s %s", action, arg)
            return None, None, None
        elif action in ["set-label", "set-var", "set-env"]:
            target = arg
            continue
        else:
            logg.error("unknown edit command starting with %s", action)
            return None, None, None
    if not inp:
        logg.error("no input image given - use 'FROM image-name'")
        return None, None, None
    if not out:
        logg.error("no output image given - use 'INTO image-name'")
        return None, None, None
    return inp, out, commands

if __name__ == "__main__":
    from optparse import OptionParser
    cmdline = OptionParser("%prog input-image output-image [commands...]")
    cmdline.add_option("-T", "--tmpdir", metavar="DIR", default=TMPDIR,
       help="use this base temp dir %s [%default]" )
    cmdline.add_option("-k", "--keepdir", action="count", default=KEEPDIR,
       help="keep the unpacked dirs [%default]")
    cmdline.add_option("-v", "--verbose", action="count", default=0,
       help="increase logging level [%default]")
    cmdline.add_option("-z", "--dryrun", action="store_true", default=not OK,
       help="only run logic, do not change anything [%default]")
    cmdline.add_option("--with-null", metavar="name", default=NULL,
       help="specify the special value for disable [%default]")
    opt, args = cmdline.parse_args()
    logging.basicConfig(level = max(0, logging.ERROR - 10 * opt.verbose))
    TMPDIR = opt.tmpdir
    KEEPDIR = opt.keepdir
    OK = not opt.dryrun
    NULL = opt.with_null
    if len(args) < 2:
        logg.error("not enough arguments, use --help")
    else:
        inp, out, commands = parsing(args)
        if not commands:
            logg.warning("nothing to do for %s", out)
            if inp and out and inp != out:
               cmd = "docker tag {inp} {out}"
               logg.info("%s", cmd)
               sh("docker tag {inp} {out}".format(**locals()), check = False)
        else:
            if opt.dryrun:
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
            edit_image(inp, out, commands)
