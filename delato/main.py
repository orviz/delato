import sys
import delato.config
import delato.log
import delato.zabbix

from oslo.config import cfg

CONF = cfg.CONF

def main():
    delato.config.parse_args(sys.argv)
    delato.log.setup_logging()

    zabbix = delato.zabbix.Zabbix()
    zabbix.collect()

if __name__ == "__main__":
    main()
