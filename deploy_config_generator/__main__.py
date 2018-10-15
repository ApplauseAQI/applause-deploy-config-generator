#!/usr/bin/env python

import argparse
import os.path
import sys
import yaml
import importlib
import pkgutil

import deploy_config_generator.output as output_ns
from deploy_config_generator.display import Display
from deploy_config_generator.vars import Vars
from deploy_config_generator.errors import DeployConfigError, ConfigGenerationError

DISPLAY = None


def find_deploy_dir(path):
    if not os.path.isdir(path):
        DISPLAY.display('Path %s is not a directory' % path)
        sys.exit(1)
    deploy_dir = os.path.join(path, 'deploy')
    if not os.path.isdir(deploy_dir):
        DISPLAY.display('Deploy dir could not be found in %s' % path)
        sys.exit(1)
    return deploy_dir


def load_deploy_config(deploy_dir, varset):
    yaml_content = ''
    with open(os.path.join(deploy_dir, 'config.yml')) as f:
        for line in f:
            yaml_content += varset.replace_vars(line)
    obj = yaml.load(yaml_content)
    # Wrap the config in a list if it's not already a list
    # This makes it easier to process
    if not isinstance(obj, list):
        obj = [ obj ]
    return obj


def find_vars_files(path, cluster):
    ret = []
    vars_dir = os.path.join(path, 'var')
    for foo in ('defaults.var', '%s.var' % cluster):
        var_file = os.path.join(vars_dir, foo)
        if os.path.isfile(var_file):
            ret.append(var_file)
    return ret


def load_output_plugins(varset, output_dir):
    plugins = []
    for finder, name, ispkg in pkgutil.iter_modules(output_ns.__path__, output_ns.__name__ + '.'):
        try:
            mod = importlib.import_module(name)
            plugins.append(getattr(mod, 'OutputPlugin')(varset, output_dir, DISPLAY))
        except Exception as e:
            DISPLAY.display('Failed to load output plugin %s: %s' % (name, str(e)))
    return plugins


def app_validate_fields(app, app_index, output_plugins):
    try:
        # Validate all fields
        for field in app:
            valid_field = False
            for plugin in output_plugins:
                if plugin.has_field(field) and plugin.is_needed(app):
                    valid_field = True
                    break
            if not valid_field:
                raise DeployConfigError("field '%s' in application %d is not valid for relevant output plugins" % (field, app_index + 1))
    except DeployConfigError as e:
        DISPLAY.display('Failed to load deploy config: %s' % str(e))


def app_render_output(app, app_index, output_plugins):
    try:
        for plugin in output_plugins:
            if plugin.is_needed(app):
                plugin.generate(app, app_index + 1)
    except ConfigGenerationError as e:
        DISPLAY.display('Failed to generate deploy config: %s' % str(e))


def main():
    global DISPLAY

    parser = argparse.ArgumentParser()
    parser.add_argument(
        'path',
        help='Path to service dir',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        help='Increase verbosity level',
    )
    parser.add_argument(
        '-c', '--cluster',
        help="Cluster to generate deploy configs for (defaults to 'local')",
        default='local'
    )
    parser.add_argument(
        '-o', '--output-dir',
        help="Directory to output generated deploy configs to (defaults to '.')",
        default='.'
    )
    args = parser.parse_args()

    DISPLAY = Display(args.verbose)

    DISPLAY.display('Running with args:', 3)
    DISPLAY.display('', 3)
    for arg in dir(args):
        if arg.startswith('_'):
            continue
        DISPLAY.display('%s: %s' % (arg, getattr(args, arg)), 3)
    DISPLAY.display('', 3)

    varset = Vars()

    output_plugins = load_output_plugins(varset, args.output_dir)

    DISPLAY.vvv('Available output plugins:')
    DISPLAY.vvv()
    for plugin in output_plugins:
        DISPLAY.vvv('- %s (%s)' % (plugin.NAME, plugin.DESCR or 'No description'))
    DISPLAY.vvv()

    deploy_dir = find_deploy_dir(args.path)
    vars_files = find_vars_files(deploy_dir, args.cluster)

    for vars_file in vars_files:
        DISPLAY.v('Loading vars from %s' % vars_file)
        varset.read_vars_file(vars_file)

    DISPLAY.vv()
    DISPLAY.vv('Vars:')
    DISPLAY.vv()
    DISPLAY.vv(yaml.dump(dict(varset), default_flow_style=False, indent=2))

    deploy_config = load_deploy_config(deploy_dir, varset)

    DISPLAY.vvv('Deploy config:')
    DISPLAY.vvv()
    DISPLAY.vvv(yaml.dump(deploy_config, default_flow_style=False, indent=2))

    for app_idx, app in enumerate(deploy_config):
        app_validate_fields(app, app_idx, output_plugins)
        app_render_output(app, app_idx, output_plugins)


if __name__ == '__main__':
    main()
