#!/usr/bin/env python3
import os
import subprocess
import sys
import argparse
import argh
import json

configFileName = '.concord.json'

def loadConfig(startingDir):
    '''
    Load config from file.
    '''
    # Find the first config file in directory tree starting from startingDir 
    # and going up
    configFilePath = None
    dirStack = []
    wd = startingDir
    homeDir = os.path.expanduser('~')
    while wd != homeDir:
        if os.path.exists(configFileName):
            configFilePath = os.path.join(wd, configFileName)
            break
        else:
            dirStack.append(wd.split('/')[-1])
            os.chdir('..')
            wd = os.getcwd()

    if configFilePath is None:
        raise ConfigFileError('No .concord.json file found up till '
                + homeDir)

    # Read config file 
    config = json.load(open(configFilePath))
    config['configDir'] = wd
    if 'remote' not in config:
        raise ConfigFileError('Required config parameter "remote" + ' +
                'is missing')
    if not config['remote'].endswith('/'):
        config['remote'] += '/'
    #for d in reversed(dirStack):
    #    config['remote'] += d + '/'

    #for backupDir in ['remote-backup-dir', 'local-backup-dir']:
    #    if backupDir in config:
    #        for d in reversed(dirStack):
    #            config[backupDir] += d + '/'


    # Restore original working directory
    os.chdir(startingDir)

    return config


defaultOptions = \
[
    'archive',
    'verbose',
    'compress',
    'progress',
    'delete-after',
    'update',
    'itemize-changes',
    'human-readable',
    'no-perms'
]


def askYesOrNoQuestion(question):
    try:
        cfm = input(question + ' (y/n): ')
        while cfm != 'y' and cfm != 'n':
            cfm = input('Please type y or n: ')
        return cfm
    except KeyboardInterrupt:
        sys.stdout.write('\n')
        raise

def sync(command, group, checkOnly, verbose):
    # Read remote from config file
    config = loadConfig(os.getcwd())

    if group and 'group' not in config:
        sys.stderr.write('No group defined in config file.\n')
        return
    
    # Assemble a list of source directories to sync
    sourceDirs = []
    if group:
        os.chdir(config['configDir'])
        startingDir = os.getcwd()
        for member in config['group']:
            if not os.path.exists(member):
                os.makedirs(member)
            sourceDirs.append(member)
    else:
        member = os.getcwd()
        os.chdir(config['configDir'])
        sourceDirs.append(member[len(config['configDir']) + 1:])

    #
    # Assemble options
    #

    options = defaultOptions[:]

    # Exclude as specified in config file
    if 'exclude' in config:
        for ex in config['exclude']:
            options.append('exclude="' + ex + '"')

    # Include source directories
    added = set()
    for sourceDir in sourceDirs:
        # Include all intermediate directories
        parts = sourceDir.split('/')
        for i in range(len(parts)):
            d = '/'.join(parts[:i+1])
            if d not in added:
                options.append('include="{}"'.format(d))
                added.add(d)

        # Include recursively in
        options.append('include="{}/**"'.format(sourceDir))

    # Excluding everything else
    options.append('exclude="*"')

    # Specify backup directory if configured
    if command == 'pull' and 'local-backup-dir' in config:
        options += ['backup', 'backup-dir=' + config['local-backup-dir']]
    if command == 'push' and 'remote-backup-dir' in config:
        options += ['backup', 'backup-dir=' + config['remote-backup-dir']]
    options = ['--' + opt for opt in options]

    cmd = 'rsync {} '.format(' '.join(options))

    anythingToSync = doSync(config, command, cmd, True, verbose)
    if not anythingToSync:
        print('Already up to date.')
    elif not checkOnly:
        confirm = askYesOrNoQuestion('This was a dry-run. Are you sure you ' +
            'want to perform this ' + command + '?')
        if confirm == 'y':
            doSync(config, command, cmd, False, verbose) 


def doSync(config, command, cmd, dryRun, verbose):
    if dryRun:
        cmd += '--dry-run '
    if command == 'push':
        cmd += '{}/ {}'.format(config['configDir'], config['remote'])
    elif command == 'pull':
        cmd += '{} {}/'.format(config['remote'], os.getcwd())
    if verbose:
        print(cmd)
    output = subprocess.check_output(cmd, shell=True,
            stderr=subprocess.STDOUT)
    output = output.decode('utf-8')
    p = output.find('files to consider')
    output = output[p + len('files to consider'):]
    combos = [
        '<f', '>f', 'cf', 'hf', '.f', 
        '<d', '>d', 'cd', 'hd', '.d', 
        '<L', '>L', 'cL', 'hL', '.L', 
        '<D', '>D', 'cD', 'hD', '.D', 
        '<S', '>S', 'cS', 'hS', '.S', 
        '*deleting'
    ]
    if all([output.find(combo) == -1 for combo in combos]):
        return False
    else:
        print(output)
        return True


def push(group=False, checkOnly=False, verbose=False):
    try:
        sync('push', group, checkOnly, verbose)
    except KeyboardInterrupt:
        pass


def pull(group=False, checkOnly=False, verbose=False):
    try:
        sync('pull', group, checkOnly, verbose)
    except KeyboardInterrupt:
        pass


def main():
    parser = argparse.ArgumentParser()

    # Add commands
    argh.add_commands(parser, [push, pull])

    # Dispatch command
    argh.dispatch(parser)


if __name__ == '__main__':
    main()
