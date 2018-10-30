from deploy_config_generator.output import OutputPluginBase


class OutputPlugin(OutputPluginBase):

    NAME = 'dummy'
    DESCR = 'Dummy output plugin for testing'
    FILE_EXT = '.foo'

    DEFAULT_CONFIG = {
        'fields': {
            'name': {
                'required': True,
            },
            'dummy': {
                'default': False,
            },
        }
    }

    TEMPLATE = '''
    Dummy output plugins

    Vars:

    {{ VARS }}

    Site config:

    {{ CONFIG.get_config() }}

    App config:

    {{ APP }}

    SERVICE_NAME = {{ VARS.SERVICE_NAME | default('N/A') }}
    '''

#    def is_needed(self, config):
#        if 'dummy' in config:
#            return True
#        return False
