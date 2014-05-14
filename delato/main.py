import os
import sys

import delato.config
import delato.log
import delato.threads
import delato.request_tracker

from oslo.config import cfg

CONF = cfg.CONF

def main():
    try:
        delato.config.parse_args(sys.argv, default_config_files=["/etc/delato.conf"])
    except cfg.ConfigFilesNotFoundError:
        cfgfile = CONF.config_file[-1] if CONF.config_file else None
        print "Could not find configuration file %s." % cfgfile
        sys.exit(-1)
    delato.log.setup_logging()

    its = delato.request_tracker.RequestTracker()
    mon = delato.zabbix.Zabbix()

    l = []
    try: 
        for t in [ 
            delato.threads.TicketCreatorThread(its, mon),
            delato.threads.TicketReminderThread(its),
        ]:
            t.start()
            l.append(t)
        
        for i in xrange(0,len(l)):
            while l[i].is_alive():
                l[i].join(10)
    except KeyboardInterrupt:
        print "Exit on user request."
        for t in l:
            t.event.set()
            t.join()

if __name__ == "__main__":
    main()
