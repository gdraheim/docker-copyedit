#! /usr/bin/python
from __future__ import print_function

__copyright__ = "(C) 2017-2018 Guido U. Draheim, licensed under the EUPL"
__version__ = "1.1.1176"

import subprocess
import collections
import os
import json
import copy
import shutil
import hashlib
import logging
from fnmatch import fnmatchcase as fnmatch

logg = logging.getLogger("edit")

TMPDIR = "load.tmp"
KEEPDIR = 0
OK=True

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

def edit_image(inp, out, edits):
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
	    changed = edit_datadir(datadir, out, edits)
	    if changed:
	        outfile = os.path.realpath(outputfile)
	        cmd = "cd {datadir} && tar cf {outfile} ."
	        sh(cmd.format(**locals()))
	        cmd = "docker load -i {outputfile}"
	        sh(cmd.format(**locals()))
	    else:
	        logg.warning("unchanged image from %s", inp)
	        if inp != out:
	            cmd = "docker tag {inp} {out}"
	            sh(cmd.format(**locals()))
	            logg.warning(" tagged old image as %s", out)
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
	    logg.debug("container_config: %s", config['container_config'])
	    CONFIG = 'config'
	    if 'Config' in config:
	        CONFIG = 'Config'
	    for action, target, arg in edits:
	        if action in ["remove", "rm"] and target in ["all"]:
	            if arg in ["volumes", "ports"]:
	                target, arg = arg, "*"
	            else:
	                logg.error("all is equivalent to '*' pattern for 'volumes' or 'ports'")
	        if action in ["remove", "rm"] and target in ["volume", "volumes"]:
		    key = 'Volumes'
		    if target in ["volumes"] and arg in ["ALL", "*", "%"]:
		        args = []
		        try:
		            if config[CONFIG][key] is not None:
		                del config[CONFIG][key]
		            logg.warning("done actual config %s %s '%s'", action, target, arg)
		        except KeyError, e:
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
		        except KeyError, e:
		            logg.warning("there was no '%s' in '%s' of  %s", entry, key, config_filename)
	        if action in ["remove", "rm"] and target in ["port", "ports"]:
		    key = 'ExposedPorts'
		    if target in ["ports"] and arg in ["ALL", "*", "%"]:
		        args = []
		        try:
		            del config[CONFIG][key]
		            logg.warning("done actual config %s %s %s", action, target, arg)
		        except KeyError, e:
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
		        entry = "%s/%s" % (port, prot)
		        try:
		            del config[CONFIG][key][entry]
		        except KeyError, e:
		            logg.warning("there was no '%s' in '%s' of  %s", entry, key, config_filename)
	        if action in ["append", "add"] and target in ["volume"]:
	            key = 'Volumes'
	            entry = os.path.normpath(arg)
	            if key not in config[CONFIG]:
	                config[CONFIG][key] = {}
	            if arg not in config[CONFIG][key]:
	                config[CONFIG][key][entry] = {}
	                logg.info("added %s to %s", entry
	                , key)
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
		        if action in ["set-shell"]:
		            running = [ "/bin/sh", "-c", arg ]
		        elif arg.startswith("["):
		            running = json.loads(arg)
		        elif arg in ["", "null", "NULL" ]:
		            running = None
		        else:
		            running = [ arg ]
		        config[CONFIG][key] = running
		        logg.warning("done edit %s %s", action, arg)
		    except KeyError, e:
		        logg.warning("there was no '%s' in %s", key, config_filename)
	        if action in ["set", "set-shell"] and target in ["cmd"]:
		    key = 'Cmd'
		    try:
		        if action in ["set-shell"]:
		            running = [ "/bin/sh", "-c", arg ]
		            logg.info("%s %s", action, running)
		        elif arg.startswith("["):
		            running = json.loads(arg)
		        elif arg in ["", "null", "NULL" ]:
		            running = None
		        else:
		            running = [ arg ]
		        config[CONFIG][key] = running
		        logg.warning("done edit %s %s", action, arg)
		    except KeyError, e:
		        logg.warning("there was no '%s' in %s", key, config_filename)
	        if action in ["remove-label", "rm-label"]:
		    key = "Labels"
		    try:
		        if key in config[CONFIG]:
		            del config[CONFIG][key][target]
		            logg.warning("done actual %s %s '%s'", action, target, arg)
		    except KeyError, e:
		        logg.warning("there was no label %s in %s", target, config_filename)
	        if action in ["set-label"]:
		    key = "Labels"
		    try:
		        if arg in ["", "null", "NULL" ]:
		            value = u''
		        else:
		            value = arg
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
		    except KeyError, e:
		        logg.warning("there was no config %s in %s", target, config_filename)
	        if action in ["set"] and target in StringConfigs:
		    key = StringConfigs[target]
		    try:
		        if arg in ["", "null", "NULL" ]:
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
		    except KeyError, e:
		        logg.warning("there was no config %s in %s", target, config_filename)
	        if action in ["set"] and target in StringMeta:
		    key = StringMeta[target]
		    try:
		        if arg in ["", "null", "NULL" ]:
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
		    except KeyError, e:
		        logg.warning("there was no meta %s in %s", target, config_filename)
	    logg.debug("resulting config: %s", config['container_config'])
	    new_config_text = json.dumps(config)
	    if new_config_text != old_config_text:
	        new_config_md = hashlib.sha256()
	        new_config_md.update(new_config_text)
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
	            fp.write(new_config_text)
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
	    fp.write(manifest_text)
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
    for n in xrange(len(args)):
        arg = args[n]
        if target is not None:
            commands.append((action, target, arg))
            action, target = None, None
            continue
        if action is None:
            if arg in ["and", "+", ",", "/"]:
               continue
            action = arg.lower()
            continue
        if action in ["rm-label", "remove-label"]:
            target = arg
            commands.append((action, target, None))
            action, target = None, None
            continue
        #
        if action in ["set"] and arg.lower() in ["shell", "label"]:
            action = "%s-%s" % (action, arg.lower())
            continue
        if action in ["rm", "remove"] and arg.lower() in ["label"]:
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
            if arg.lower() in StringCmd:
                target = arg.lower()
                continue
            if arg.lower() in StringConfigs:
                target = arg.lower()
                continue
            if arg.lower() in StringMeta:
                target = arg.lower()
                continue
            logg.error("unknown edit command starting with %s %s", action, arg)
            return None, None, None
        elif action in ["set-shell"]:
            if arg.lower() in StringCmd:
                target = arg.lower()
                continue
            logg.error("unknown edit command starting with %s %s", action, arg)
            return None, None, None
        elif action in ["set-label"]:
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
    opt, args = cmdline.parse_args()
    logging.basicConfig(level = max(0, logging.ERROR - 10 * opt.verbose))
    TMPDIR = opt.tmpdir
    KEEPDIR = opt.keepdir
    OK = not opt.dryrun
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
                    logg.info(" | %s %s   %s", action, target, arg)
                logg.level = oldlevel
            edit_image(inp, out, commands)
