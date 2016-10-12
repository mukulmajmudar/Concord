#!/usr/bin/env python
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
    for d in reversed(dirStack):
        config['remote'] += d + '/'

    for backupDir in ['remote-backup-dir', 'local-backup-dir']:
        if backupDir in config:
            for d in reversed(dirStack):
                config[backupDir] += d + '/'


    # Restore original working directory
    os.chdir(startingDir)

    return config

defaultShortOptions = \
[
    'a',
    'v',
    'z'
]

defaultLongOptions = \
[
    'progress',
    'delete-after',
    'update',
    'itemize-changes',
    'human-readable'
]


def askYesOrNoQuestion(question):
    try:
        cfm = raw_input(question + ' (y/n): ')
        while cfm != 'y' and cfm != 'n':
            cfm = raw_input('Please type y or n: ')
        return cfm
    except KeyboardInterrupt:
        sys.stdout.write('\n')
        raise

def doSync(config, command, cmd, dryRun, verbose):
    if dryRun:
        cmd += '--dry-run '
    if command == 'push':
        cmd += os.getcwd() + '/ ' + config['remote']
    elif command == 'pull':
        cmd += config['remote'] + ' ' + os.getcwd() + '/'
    if verbose:
        print cmd
    output = subprocess.check_output(cmd, shell=True,
            stderr=subprocess.STDOUT)
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
        print output
        return True


def sync(command, group, verbose):
    # Read remote from config file
    config = loadConfig(os.getcwd())

    if group and 'group' not in config:
        sys.stderr.write('No group defined in config file.\n')
        return

    if group:
        os.chdir(config['configDir'])
        startingDir = os.getcwd()
        # Recurse for each group member
        for member in config['group']:
            print('-- ' + command + ' for ' + member + '...')
            if not os.path.exists(member):
                os.makedirs(member)
            os.chdir(member)
            sync(command, False, verbose)
            os.chdir(startingDir)
        return

    longOptions = defaultLongOptions[:]
    if 'exclude' in config:
        for ex in config['exclude']:
            longOptions.append('exclude="' + ex + '"')

    if command == 'pull' and 'local-backup-dir' in config:
        longOptions += ['backup', 'backup-dir=' + config['local-backup-dir']]
    if command == 'push' and 'remote-backup-dir' in config:
        longOptions += ['backup', 'backup-dir=' + config['remote-backup-dir']]

    longOptions = ['--' + opt for opt in longOptions]
    shortOptions = ['-' + opt for opt in defaultShortOptions]

    cmd = 'rsync ' + ' '.join(shortOptions) + ' ' + ' '.join(longOptions) + ' '

    anythingToSync = doSync(config, command, cmd, True, verbose)
    if not anythingToSync:
        print('Already up to date.')
    else:
        confirm = askYesOrNoQuestion('This was a dry-run. Are you sure you ' +
            'want to perform this ' + command + '?')
        if confirm == 'y':
            doSync(config, command, cmd, False, verbose)


def push(group=False, verbose=False):
    try:
        sync('push', group, verbose)
    except KeyboardInterrupt:
        pass


def pull(group=False, verbose=False):
    try:
        sync('pull', group, verbose)
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
