import logging

import delato.template
import delato.exception

from oslo.config import cfg
from rtkit.authenticators import CookieAuthenticator
from rtkit.errors import RTResourceError
from rtkit.resource import RTResource
from string import Template


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
               default='AlarmID',
               help="RT custom field to store the alarm's id."),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="request_tracker")


class RequestTracker(object):
    def __init__(self):
        self.conn  = self._connect()
        self.cache = self._create_cache()
        print self.cache

    def _connect(self):
        return RTResource('%s/REST/1.0/' % CONF.request_tracker.url,
                          CONF.request_tracker.username, 
                          CONF.request_tracker.password, 
                          CookieAuthenticator)
   
    def _create_cache(self):
        """Stores the open tickets in memory."""
        response = self.conn.get(path=("search/ticket?query=Queue='%s'"
                                        "+AND+(Status='new'+OR+Status='"
                                        "open'+OR+Status='stalled')" 
                                        % CONF.request_tracker.queue))
        l = []
        for t in response.parsed[0]:
            id, title = t
            l.append(dict(self.conn.get(path="ticket/%s" % id).parsed[0]))
        return l

    def _find(self, alarm_id):
        """Searches for a ticket that contains the <alarm_id>.

           Returns a dictionary with the ticket's fields if found.
        """
        logger.debug("Searching for a ticket with alarm ID <%s>" % alarm_id)
        for t in self.cache:
            try:
                if t['CF.{%s}' % CONF.request_tracker.alarm_custom_field] == alarm_id:
                    logger.info("Found a matching ticket: %s" % t)
                    return t
                else:
                    kk = t['CF.{%s}' % CONF.request_tracker.alarm_custom_field]
                    logging.info("Theorically not mached relation: (%s, %s)" % (kk, alarm_id))
            except KeyError:
                logger.debug("Ticket %s has no <%s> custom field defined" 
                             % (t, CONF.request_tracker.alarm_custom_field))
            logger.info("No matching ticket found for alarm ID <%s>" % alarm_id)
        return False


    def create_ticket(self, alarm_id, **kwargs):
        """Creates a new ticket.

           <alarm_id> is an unique ID that identifies the alarm, so that
                      this alarm are only mapped to one ticket.
           KWARGS     must contain the keys being used in the templates.
        """
        kwargs.update({"alarm_id": alarm_id})
        logger.debug("Keyword arguments: %s" % kwargs)
        try:
            content = {
                'content': {
                    'Queue'  : CONF.request_tracker.queue,
                    'Subject': Template(CONF.request_tracker.new_subject).substitute(kwargs),
                    'Text'   : Template(CONF.request_tracker.new_body).substitute(kwargs),
                }
            }
        except KeyError, e:
            raise delato.exception.MissingTemplateArgument(str(e))

        if CONF.request_tracker.alarm_custom_field: 
            content["content"]["CF-%s" % CONF.request_tracker.alarm_custom_field] = alarm_id
       
        logger.debug("Ticket content: %s" % content["content"])
        if not self._find(alarm_id):
            logging.info("Creating ticket for alarm ID: %s" % alarm_id)
            try:
                response = self.conn.post(path='ticket/new', payload=content,)
                logger.info("Ticket created: %s" % dir(response))
                logger.info("Ticket status: %s" % response.status)
                logger.info("Ticket status int: %s" % response.status_int)
                logger.info("Ticket body: %s" % response.body)
                logger.info("Ticket parsed: %s" % response.parsed)
                if response.status_int != 200:
                    raise delato.exception.CreateTicketException(response.status)
                ticket_id = response.parsed[0][0][1].split("/")[1]
                logger.info("Ticket %s has been successfully created" % ticket_id)
            except RTResourceError as e:
                logger.error(e.response.status_int)
                logger.error(e.response.status)
                logger.error(e.response.parsed)
        else:
            logging.debug("Not creating ticket for alarm ID <%s>" % alarm_id)
