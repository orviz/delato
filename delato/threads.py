import logging
import threading
import time

import delato.request_tracker
import delato.zabbix

from oslo.config import cfg


logger = logging.getLogger(__name__)


opts = [
    cfg.BoolOpt('invalidate_tickets',
               default=False,
               help='Invalidates all the tickets being created by delato.'),
]

CONF = cfg.CONF
CONF.register_opts(opts)


class TicketReminderThread(threading.Thread):
    def __init__(self, its):
        super(TicketReminderThread, self).__init__()
        self.event = threading.Event()
        self.its = its

    def run(self):
        # FIXME These threads must start at different stages. If not the cache
        # will be updated twice at the thread start. 
        time.sleep(20)
        reminder_update = delato.request_tracker.CONF.request_tracker.reminder_update
        if reminder_update:
            pattern = '%a %b %d %H:%M:%S %Y'

            while not self.event.is_set():
                for t in self.its.cache:
                    last_updated_epoch = time.mktime(time.strptime(t['LastUpdated'], pattern))
                    if time.time()-last_updated_epoch > reminder_update:
                        self.its.comment(t["id"])
                
                self.event.wait(10)
        else:
            logger.info("Reminder capabilities are not enabled.")
            logger.debug("Not starting TicketReminderThread.")
        logger.info("Exiting from TicketReminderThread.")


class TicketCreatorThread(threading.Thread): 
    def __init__(self, its, mon):
        super(TicketCreatorThread, self).__init__()
        self.event = threading.Event()
        self.its = its
        self.mon = mon

    def run(self):
        if CONF.invalidate_tickets:
            self.its.set_status([d["id"] for d in self.its.cache], "rejected")

        while not self.event.is_set():
            for d in self.mon.collect():
                expiration_in_epoch = float(d["lastchange"])
                if time.time()-expiration_in_epoch > float(d["expiration"]):
                    logger.info("Zabbix trigger (%s) is above the due date limit (%s)"
                                 % (d, d["expiration"]))
                    
                    if [_d for _d in self.its.cache if _d["CF.{%s}" % self.its.custom_field] == d["triggerid"]]:
                        logger.debug("Ticket for alarm ID <%s> already exists" % d["triggerid"])
                    else:
                        self.its.create(d["triggerid"],
                                         description = d["description"],
                                         host        = d["hostname"], 
                                         age         = time.ctime(float(d["lastchange"])),
                                         severity    = d["severity"],
                                         expiration  = d["expiration"])

            self.event.wait(10)
        logger.info("Exiting from TicketCreatorThread.")

