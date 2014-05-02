import logging
import requests
import time

from oslo.config import cfg
from pyzabbix import ZabbixAPI

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

opts = [
    cfg.StrOpt('url',
               default='http://localhost',
               help='Zabbix base URL.'),
    cfg.StrOpt('username',
               default='',
               help='User to authenticate as.'),
    cfg.StrOpt('password',
               default='',
               help='Password to authenticate with.'),
    cfg.IntOpt('severity_5',
               default='',
               help='Age limit of severity/priority 5.'),
    cfg.IntOpt('severity_4',
               default='',
               help='Age limit of severity/priority 4.'),
    cfg.IntOpt('severity_3',
               default='',
               help='Age limit of severity/priority 3.'),
    cfg.IntOpt('severity_2',
               default='',
               help='Age limit of severity/priority 2.'),
    cfg.IntOpt('severity_1',
               default='',
               help='Age limit of severity/priority 1.'),
    cfg.IntOpt('severity_0',
               default='',
               help='Age limit of severity/priority 0.'),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="zabbix")


class Zabbix(object):
    def _connect(self):
        s = requests.Session()
        s.auth = (CONF.zabbix.username, CONF.zabbix.password)
        s.verify = False
        conn = ZabbixAPI(CONF.zabbix.url, s)
        conn.login(CONF.zabbix.username, CONF.zabbix.password)

        return conn

    def _get_triggers(self, priority=None, wrong_only=True):
        conn = self._connect()
        logger.debug("Connected to Zabbix API Version %s" % conn.api_version())

        kw = {}
        if wrong_only:
            kw["filter"] = { "value": 1 }
        if priority:
            try:
                kw["filter"].update({ "priority": priority })
            except KeyError:
                kw["filter"] = { "priority": priority }
        return conn.trigger.get(
                output=["triggerid", "description", "priority", "value", "lastchange"],
                expandData="extend",
                withUnacknowledgedEvents=1,
                #withLastEventUnacknowledged=1,
                #only_true=1,
                #active=1,
                monitored=1,
                **kw)

    def collect(self):
        for severity, age in [(0, CONF.zabbix.severity_0),
                              (1, CONF.zabbix.severity_1),
                              (2, CONF.zabbix.severity_2),
                              (3, CONF.zabbix.severity_3),
                              (4, CONF.zabbix.severity_4),
                              (5, CONF.zabbix.severity_5),]:
            if age:
                for d in self._get_triggers(priority=severity):
                    age_in_epoch = float(d["lastchange"])
                    if time.time()-age_in_epoch > age:
                        logger.debug("Zabbix trigger (%s) is above the age limit (%s)"
                                     % (d, age))
