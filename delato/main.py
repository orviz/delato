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
        print "Could not find configuration file %s" % cfgfile
        sys.exit(-1)
    delato.log.setup_logging()

    t_alarm = delato.threads.TicketCreatorThread()
    t_alarm.start()
    t_alarm.join()

    t_reminder = delato.threads.TicketReminderThread()
    t_reminder.start()
    t_reminder.join()

if __name__ == "__main__":
    main()
