import re

from deploy_config_generator.utils import json_dump
from deploy_config_generator.output import OutputPluginBase


class OutputPlugin(OutputPluginBase):

    NAME = 'marathon'
    DESCR = 'Marathon output plugin'
    FILE_EXT = '.json'

    DEFAULT_CONFIG = {
        'fields': {
            'apps': {
                'id': dict(
                    required=True,
                ),
                'image': dict(
                    required=True,
                ),
                'cpus': dict(
                    required=True,
                ),
                'mem': dict(
                    required=True,
                ),
                'disk': dict(
                    required=True,
                ),
                'instances': dict(
                    default=1,
                ),
                'constraints': dict(
                    type='list',
                ),
                'ports': dict(
                    type='list',
                    subtype='dict',
                    fields=dict(
                        container_port=dict(
                            type='int',
                            required=True,
                        ),
                        host_port=dict(
                            type='int',
                            default=0,
                        ),
                        service_port=dict(
                            type='int',
                            default=0,
                        ),
                        protocol=dict(
                            type='str',
                            default='tcp',
                        ),
                        labels=dict(
                            type='list',
                            subtype='dict',
                            fields=dict(
                                name={},
                                value={},
                                condition={},
                            ),
                        ),
                    ),
                ),
                'env': {},
                'health_checks': dict(
                    type='list',
                    subtype='dict',
                    fields=dict(
                        port_index=dict(
                            type='int',
                        ),
                        protocol=dict(
                            default='MESOS_HTTP',
                        ),
                        grace_period_seconds=dict(
                            type='int',
                        ),
                        interval_seconds=dict(
                            type='int',
                        ),
                        timeout_seconds=dict(
                            type='int',
                        ),
                        max_consecutive_failures=dict(
                            type='int',
                        ),
                        command=dict(
                            type='str',
                        ),
                        path=dict(
                            type='str',
                        ),
                    ),
                ),
                'labels': {},
                'container_labels': {},
                'fetch': dict(
                    type='list',
                    subtype='dict',
                ),
                'upgrade_strategy': dict(
                    type='dict',
                    fields=dict(
                        minimum_health_capacity=dict(
                            type='float',
                        ),
                        maximum_over_capacity=dict(
                            type='float',
                        ),
                    ),
                ),
                'unreachable_strategy': dict(
                    type='dict',
                    fields=dict(
                        inactive_after_seconds=dict(
                            type='int',
                        ),
                        expunge_after_seconds=dict(
                            type='int',
                        ),
                    ),
                ),
            }
        }
    }

    def underscore_to_camelcase(self, value):
        '''
        Convert field name with underscores to camel case

        This converts 'foo_bar_baz' (the standard for this app) to
        'fooBarBaz' (the standard for Marathon)
        '''
        def replacer(match):
            # Grab the last character of the match and upper-case it
            return match.group(0)[-1].upper()
        return re.sub(r'_[a-z]', replacer, value)

    def generate_output(self, app_vars):
        # Basic structure
        data = {
            "id": "{{ APP.id }}",
            "cpus": '{{ APP.cpus | output_float }}',
            "mem": '{{ APP.mem | output_int }}',
            "disk": '{{ APP.disk | output_int }}',
            "instances": '{{ APP.instances | output_int }}',
            # TODO: add support for container types other than 'DOCKER'
            "container": {
                "type": "DOCKER",
                "volumes": [],
                # TODO: make various attributes configurable
                "docker": {
                    "image": "{{ APP.image }}",
                    "network": "BRIDGE",
                    "privileged": False,
                    "parameters": [],
                    "forcePullImage": True
                }
            },
        }
        # Constraints
        if app_vars['APP']['constraints']:
            data['constraints'] = app_vars['APP']['constraints']
        # Ports
        self.build_port_mappings(app_vars, data)
        # Container labels
        self.build_container_labels(app_vars, data)
        # Environment
        if app_vars['APP']['env'] is not None:
            data['env'] = app_vars['APP']['env']
        # Fetch config
        self.build_fetch_config(app_vars, data)
        # Health checks
        self.build_health_checks(app_vars, data)
        # Upgrade/unreachable strategies
        self.build_upgrade_strategy(app_vars, data)
        self.build_unreachable_strategy(app_vars, data)
        # Labels
        if app_vars['APP']['labels'] is not None:
            data['labels'] = app_vars['APP']['labels']

        output = json_dump(self._template.render_template(data, app_vars))
        return output

    def build_container_labels(self, app_vars, data):
        if app_vars['APP']['container_labels'] is not None:
            container_parameters = []
            for label_index, label in enumerate(app_vars['APP']['container_labels']):
                tmp_param = {
                    "key": "label",
                    "value": label
                }
                container_parameters.append(tmp_param)
            data['container']['docker']['parameters'] = container_parameters

    def build_port_mappings(self, app_vars, data):
        port_mappings = []
        tmp_vars = app_vars.copy()
        for port_index, port in enumerate(app_vars['APP']['ports']):
            tmp_vars.update(dict(port=port, port_index=port_index))
            tmp_port = {
                "protocol": port['protocol'],
            }
            for field in ('container_port', 'host_port', 'service_port'):
                if port[field] is not None:
                    tmp_port[field] = int(port[field])
            # Port labels
            port_labels = {}
            for label_index, label in enumerate(port['labels']):
                tmp_vars.update(dict(label=label, label_index=label_index))
                if 'condition' not in label or self._template.evaluate_condition(label['condition'], tmp_vars):
                    port_labels[self._template.render_template(label['name'], tmp_vars)] = self._template.render_template(label['value'], tmp_vars)
            if port_labels:
                tmp_port['labels'] = port_labels
            # Render templates now so that loop vars can be used
            tmp_port = self._template.render_template(tmp_port, tmp_vars)
            port_mappings.append(tmp_port)
        if port_mappings:
            data['container']['docker']['portMappings'] = port_mappings

    def build_fetch_config(self, app_vars, data):
        fetch_config = []
        tmp_vars = app_vars.copy()
        for fetch_index, fetch in enumerate(app_vars['APP']['fetch']):
            tmp_vars.update(dict(fetch=fetch, fetch_index=fetch_index))
            if not ('condition' in fetch) or self._template.evaluate_condition(fetch['condition'], tmp_vars):
                tmp_fetch = fetch.copy()
                if 'condition' in tmp_fetch:
                    del tmp_fetch['condition']
                fetch_config.append(tmp_fetch)
        if fetch_config:
            data['fetch'] = fetch_config

    def build_health_checks(self, app_vars, data):
        health_checks = []
        tmp_vars = app_vars.copy()
        for check_index, check in enumerate(app_vars['APP']['health_checks']):
            tmp_vars.update(dict(check=check, check_index=check_index))
            tmp_check = {}
            for field in ('grace_period_seconds', 'interval_seconds', 'timeout_seconds', 'max_consecutive_failures', 'path', 'port_index', 'protocol'):
                if check[field] is not None:
                    tmp_check[self.underscore_to_camelcase(field)] = check[field]
            if check['command'] is not None:
                tmp_check.update(dict(
                    protocol='COMMAND',
                    command=dict(
                        value=check['command']
                    )
                ))
            # Render templates now so that loop vars can be used
            tmp_check = self._template.render_template(tmp_check, tmp_vars)
            health_checks.append(tmp_check)
        if health_checks:
            data['healthChecks'] = health_checks

    def build_upgrade_strategy(self, app_vars, data):
        strategy = {}
        app_vars_section = app_vars['APP']['upgrade_strategy']
        for field in ('minimum_health_capacity', 'maximum_over_capacity'):
            if app_vars_section[field] is not None:
                strategy[self.underscore_to_camelcase(field)] = float(app_vars_section[field])
        if strategy:
            data['upgradeStrategy'] = strategy

    def build_unreachable_strategy(self, app_vars, data):
        strategy = {}
        app_vars_section = app_vars['APP']['unreachable_strategy']
        for field in ('inactive_after_seconds', 'expunge_after_seconds'):
            if app_vars_section[field] is not None:
                strategy[self.underscore_to_camelcase(field)] = int(app_vars_section[field])
        if strategy:
            data['unreachableStrategy'] = strategy
