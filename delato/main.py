import sys

from oslo.config import cfg
import delato.config
import delato.zabbix

CONF = cfg.CONF

def main():
    delato.config.parse_args(sys.argv)
    zabbix = delato.zabbix.Zabbix()
    zabbix.collect()

if __name__ == "__main__":
    main()
