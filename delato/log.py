import logging
import logging.handlers
import os

from oslo.config import cfg

common_cli_opts = [    
    cfg.BoolOpt('debug',
                short='d',
                default=False,
                help='Print debugging output (set logging level to '
                     'DEBUG instead of default WARNING level).'),
    cfg.BoolOpt('verbose',
                short='v',
                default=False,
                help='Print more verbose output (set logging level to '
                     'INFO instead of default WARNING level).'),
]

opts = [
    cfg.BoolOpt('use_stderr',
                default=True,
                help='Log output to standard error'),
    cfg.BoolOpt('use_syslog',
                default=False,
                help='Log output to syslog'),
    cfg.StrOpt('log_to_file',
                default='',
                help='Log output to the given file'),
]

CONF = cfg.CONF
CONF.register_cli_opts(common_cli_opts)
CONF.register_opts(opts)

def setup_logging():
    logger = logging.getLogger()

    if CONF.use_stderr:
        logger.addHandler(logging.StreamHandler(open('/dev/stderr', 'w')))
    if CONF.use_syslog:
        logger.addHandler(logging.handlers.SysLogHandler(address='/dev/log'))
    if CONF.log_to_file:
        logger.addHandler(logging.FileHandler(cfg.CONF.log_to_file))
    
    if CONF.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("Setting log level to DEBUG")
    elif CONF.verbose:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.WARNING)

