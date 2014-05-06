import logging

import delato.template

from oslo.config import cfg
from rtkit.resource import RTResource
from rtkit.authenticators import CookieAuthenticator


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
    cfg.StrOpt('queue',
               default='',
               help='Queue to work with.'),
    cfg.StrOpt('new_subject',
               default=delato.template.NEW_TICKET_SUBJECT,
               help='Subject for opening tickets.'),
    cfg.StrOpt('new_body',
               default=delato.template.NEW_TICKET_BODY,
               help='Message body for opening tickets.'),
    cfg.StrOpt('update_body',
               default=delato.template.UPDATE_TICKET_BODY,
               help='Message body for updating tickets.'),
    cfg.StrOpt('close_body',
               default=delato.template.CLOSE_TICKET_BODY,
               help='Message body for closing tickets.'),
    cfg.StrOpt('alarm_custom_field',
               default='',
               help="RT custom field to store the alarm's id."),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="request_tracker")


class RequestTracker(object):
    def _connect(self):
        return RTResource('%s/REST/1.0/' % CONF.request_tracker.url,
                          CONF.request_tracker.username, 
                          CONF.request_tracker.password, 
                          CookieAuthenticator)
   

    def _find(self, conn, alarm_id):
        """Searches for a ticket that contains the <alarm_id>.

           Returns a dictionary with the ticket's fields if found.
        """
        response = conn.get(path=("search/ticket?query=Queue='%s'"
                                  "+AND+(Status='new'+OR+Status='"
                                  "open'+OR+Status='stalled')" 
                                  % CONF.request_tracker.queue))
        logger.debug("Searching for a ticket with alarm ID <%s>" % alarm_id)
        for t in response.parsed[0]:
            id, title = t
            d = dict(conn.get(path="ticket/%s" % alarm_id).parsed[0]))
            try:
                if d['CF.{%s}' % CONF.request_tracker.alarm_custom_field] == alarm_id:
                    logger.debug("Found a matching ticket: %s" % d)
                    return d
            except KeyError:
                pass
            logger.debug("No matching ticket found for alarm ID <%s>" % alarm_id)
            return False

 
    def create_ticket(self, alarm_id):
        """Creates a new ticket.

           <alarm_id> is an unique ID that identifies the alarm, so that
           this alarm are only mapped to one ticket.
        """
        content = {
            'content': {
                'Queue'  : CONF.request_tracker.queue,
                'Subject': CONF.request_tracker.new_subject,
                'Text'   : CONF.request_tracker.new_body,
            }
        }
        if CONF.request_tracker.alarm_custom_field: 
            content['content']['CR.{%s}' % CONF.request_tracker.watermark] = alarm_id
        
        conn = self._connect()
        if not self._find(conn, alarm_id):
            try:
                response = conn.post(path='ticket/new', payload=content,)
                logger.info("Ticket created: %s" % response.parsed)
            except RTResourceError as e:
                logger.error(e.response.status_int)
                logger.error(e.response.status)
                logger.error(e.response.parsed)
