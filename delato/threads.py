import logging
import threading
import time

import delato.request_tracker


logger = logging.getLogger(__name__)


class TicketReminderThread(threading.Thread):
    def __init__(self, its=delato.request_tracker.RequestTracker):
        super(TicketReminderThread, self).__init__()
        self.event = threading.Event()
        self.its = its()

    def run(self):
        reminder_update = delato.request_tracker.CONF.request_tracker.reminder_update
        if reminder_update:
            pattern = '%a %b %d %H:%M:%S %Y'

            while not self.event.is_set():
                for t in self.its.cache:
                    last_updated_epoch = time.mktime(time.strptime(t['LastUpdated'], pattern))
                    if time.time()-last_updated_epoch > reminder_update:
                        self.its.comment(t["id"])
                
                self.its.load_cache()
                self.event.wait(10)
        else:
            logger.info("Reminder capabilities are not enabled.")
            logger.debug("Not starting TicketReminderThread.")
        logger.info("Exiting from TicketReminderThread.")


class TicketCreatorThread(threading.Thread): 
    def __init__(self, its=delato.request_tracker.RequestTracker, mon=delato.zabbix.Zabbix):
        super(AlarmToTicketThread, self).__init__()
        self.event = threading.Event()
        self.its = its()
        self.mon = mon()

    def run(self):
        while not self.event.is_set():
            for d in self.mon.collect():
                expiration_in_epoch = float(d["lastchange"])
                if time.time()-expiration_in_epoch > float(d["expiration"]):
                    logger.info("Zabbix trigger (%s) is above the due date limit (%s)"
                                 % (d, d["expiration"]))
                    
                    self.its.create(d["triggerid"],
                                     description = d["description"],
                                     host        = d["hostname"], 
                                     age         = time.ctime(float(d["lastchange"])),
                                     severity    = severity_name,
                                     expiration  = expiration,)  
            self.event.wait(10)
        logger.info("Exiting from TicketCreatorThread.")

