import sys
import delato.config
import delato.log
import delato.threads

from oslo.config import cfg

CONF = cfg.CONF

def main():
    delato.config.parse_args(sys.argv)
    delato.log.setup_logging()

    t_alarm = delato.threads.TicketCreatorThread()
    t_alarm.start()
    t_alarm.join()

    t_reminder = delato.threads.TicketReminderThread()
    t_reminder.start()
    t_reminder.join()

if __name__ == "__main__":
    main()
