import logging
import threading
import time

import delato.request_tracker


logger = logging.getLogger(__name__)


class TicketReminderThread(threading.Thread):
    def __init__(self, its=delato.request_tracker.RequestTracker):
        super(TicketReminderThread, self).__init__()
        self.its = its()
        self.event = threading.Event()

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
        logger.info("Reminder capabilities are not enabled.")
        logger.debug("Not starting TicketReminderThread.")
