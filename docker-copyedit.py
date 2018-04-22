#! /usr/bin/python
from __future__ import print_function

__copyright__ = "(C) 2016-2018 Guido U. Draheim, licensed under the EUPL"
__version__ = "1.0.1000"

import subprocess
import collections
import os
import json
import copy
import hashlib
import logging

logg = logging.getLogger("edit")

TMPDIR = "load.tmp"
OK=True

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
	if OK: edit_datadir(datadir, out, edits)
	#
	outfile = os.path.realpath(outputfile)
	cmd = "cd {datadir} && tar cf {outfile} ."
	sh(cmd.format(**locals()))
	cmd = "docker load -i {outputfile}"
	sh(cmd.format(**locals()))

def edit_datadir(datadir, out, edits):
	manifest_file = "manifest.json"
	manifest_filename = os.path.join(datadir, manifest_file)
	with open(manifest_filename) as fp:
	    manifest = json.load(fp)
	for item in xrange(len(manifest)):
	    config_file = manifest[item]["Config"]
	    config_filename = os.path.join(datadir, config_file)
	    with open(config_filename) as fp:
	        config = json.load(fp)
	    logg.debug("container_config: %s", config['container_config'])
	    section = None
	    action = None
	    for action, arg in edits:
	        if action in ["remove all"]:
	            if arg in ["volume", "volumes", "VOLUME", "VOLUMES"]:
	                action, arg = "remove volume", "all"
	            else:
	                logg.warning("no action for %s %s", action, arg)
	                logg.info("did you mean 'remove all volumes'?")
	                continue
	        if action in ["remove volume"]:
	            if arg in ["all", "ALL"]:
		        try:
		            del config['config']['Volumes']
		            logg.warning("done actual config %s %s", action, arg)
		        except KeyError, e:
		            logg.warning("there were no 'Volumes' in %s", config_filename)
		    elif arg.startswith("/"):
		        try:
		            del config['config']['Volumes'][arg]
		        except KeyError, e:
		            logg.warning("there was no '%s' in 'Volumes' of  %s", arg, config_filename)
		    else:
		        logg.error("can not do edit '%s %s'", action, arg)
		        return False
	        if action in ["set entrypoint"]:
		    try:
		        if arg.startswith("["):
		            running = json.loads(arg)
		        elif arg in ["", "null", "NULL" ]:
		            running = None
		        else:
		            running = [ arg ]
		        config['config']['Entrypoint'] = running
		        logg.warning("done edit %s %s", action, arg)
		    except KeyError, e:
		        logg.warning("there was no 'Entrypoint' in %s", config_filename)
	        if action in ["set cmd"]:
		    try:
		        if arg.startswith("["):
		            running = json.loads(arg)
		        elif arg in ["", "null", "NULL" ]:
		            running = None
		        else:
		            running = [ arg ]
		        config['config']['Cmd'] = running
		        logg.warning("done edit %s %s", action, arg)
		    except KeyError, e:
		        logg.warning("there was no 'Cmd' in %s", config_filename)
	        if action in ["set user"]:
		    try:
		        if arg.startswith("["):
		            running = json.loads(arg)
		        elif arg in ["", "null", "NULL" ]:
		            running = None
		        else:
		            running = [ arg ]
		        config['config']['User'] = running
		        logg.warning("done edit %s %s", action, arg)
		    except KeyError, e:
		        logg.warning("there was no 'User' in %s", config_filename)
	    logg.debug("container_config: %s", config['container_config'])
	    new_config_text = json.dumps(config)
	    new_config_md = hashlib.sha256()
	    new_config_md.update(new_config_text)
	    new_config_hash = new_config_md.hexdigest()
	    new_config_file = "%s.json" % new_config_hash
	    new_config_filename = os.path.join(datadir, new_config_file)
	    with open(new_config_filename, "wb") as fp:
	        fp.write(new_config_text)
	    logg.info("written new %s", new_config_filename)
	    #
	    if manifest[item]["RepoTags"]:
	        manifest[item]["RepoTags"] = [ out ]
	    manifest[item]["Config"] = new_config_file
	    os.remove(config_filename)
	    logg.info("removed old %s", config_filename)
	manifest_text = json.dumps(manifest)
	manifest_filename = os.path.join(datadir, manifest_file)
	with open(manifest_filename, "wb") as fp:
	    fp.write(manifest_text)

def parsing(args):
    inp = None
    out = None
    section = None
    action = None
    commands = []
    for arg in args:
        if action is not None:
           commands.append((action, arg))
           action, section = None, None
           continue
        if section is None:
            if arg in ["and", "+", ",", "/"]:
               continue
            section = arg.lower()
            continue
        elif section in ["from"]:
            inp = arg
            section = None
            continue
        elif section in ["into"]:
            out = arg
            section = None
            continue
        elif section in ["remove", "rm"]:
            if arg.lower() in ["volume", "all"]:
               action = "remove " + arg.lower()
               continue
            logg.error("unknown edit command starting with %s %s", section, arg)
            return None, None, None
        elif section in ["set", "override"]:
            if arg in ["cmd", "entrypoint", "user"]:
               action = "set " + arg.lower()
               continue
            logg.error("unknown edit command starting with %s %s", section, arg)
            return None, None, None
        else:
            logg.error("unknown edit command starting with %s", section)
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
    cmdline.add_option("-v", "--verbose", action="count", default=0,
       help="increase logging level [%default]")
    cmdline.add_option("-z", "--dryrun", action="store_true", default=not OK,
       help="only run logic, do not change anything [%default]")
    opt, args = cmdline.parse_args()
    logging.basicConfig(level = max(0, logging.ERROR - 10 * opt.verbose))
    TMPDIR = opt.tmpdir
    OK = not opt.dryrun
    if len(args) < 2:
        logg.error("not enough arguments, use --help")
    else:
        inp, out, commands = parsing(args)
        if not commands:
            logg.warning("nothing to do for %s", out)
        else:
            edit_image(inp, out, commands)
