import os
import sys

import delato.config
import delato.log
import delato.threads

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

    l = []
    try: 
        for t in [ 
            delato.threads.TicketCacheThread(),
            delato.threads.TicketCreatorThread(),
            delato.threads.TicketReminderThread(),
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
