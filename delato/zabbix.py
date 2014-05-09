import logging
import requests
import time
import delato.request_tracker

from oslo.config import cfg
from pyzabbix import ZabbixAPI

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
    cfg.StrOpt('severity_5_name',
               default='Disaster',
               help='Name for severity 5.'),
    cfg.IntOpt('severity_5_expiration',
               default='',
               help='Age limit of severity/priority 5.'),
    cfg.StrOpt('severity_4_name',
               default='High',
               help='Name for severity 4.'),
    cfg.IntOpt('severity_4_expiration',
               default='',
               help='Age limit of severity/priority 4.'),
    cfg.StrOpt('severity_3_name',
               default='Average',
               help='Name for severity 3.'),
    cfg.IntOpt('severity_3_expiration',
               default='',
               help='Age limit of severity/priority 3.'),
    cfg.StrOpt('severity_2_name',
               default='Warning',
               help='Name for severity 2.'),
    cfg.IntOpt('severity_2_expiration',
               default='',
               help='Age limit of severity/priority 2.'),
    cfg.StrOpt('severity_1_name',
               default='Information',
               help='Name for severity 1.'),
    cfg.IntOpt('severity_1_expiration',
               default='',
               help='Age limit of severity/priority 1.'),
    cfg.StrOpt('severity_0_name',
               default='Not Classified',
               help='Name for severity 0.'),
    cfg.IntOpt('severity_0_expiration',
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
        rt = delato.request_tracker.RequestTracker()
        for severity, severity_name, expiration in [(0,
                                      CONF.zabbix.severity_0_name,
                                      CONF.zabbix.severity_0_expiration),
                                     (1,
                                      CONF.zabbix.severity_1_name,
                                      CONF.zabbix.severity_1_expiration),
                                     (2,
                                      CONF.zabbix.severity_2_name,
                                      CONF.zabbix.severity_2_expiration),
                                     (3,
                                      CONF.zabbix.severity_3_name,
                                      CONF.zabbix.severity_3_expiration),
                                     (4,
                                      CONF.zabbix.severity_4_name,
                                      CONF.zabbix.severity_4_expiration),
                                     (5,
                                      CONF.zabbix.severity_5_name,
                                      CONF.zabbix.severity_5_expiration),]:
            if expiration:
                for d in self._get_triggers(priority=severity):
                    expiration_in_epoch = float(d["lastchange"])
                    if time.time()-expiration_in_epoch > expiration:
                        logger.info("Zabbix trigger (%s) is above the due date limit (%s)"
                                     % (d, expiration))
                        
                        rt.create(d["triggerid"],
                                         description = d["description"],
                                         host        = d["hostname"], 
                                         age         = time.ctime(float(d["lastchange"])),
                                         severity    = severity_name,
                                         expiration  = expiration,)  

