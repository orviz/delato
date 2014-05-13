import logging
import time

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
    cfg.StrOpt('alarm_custom_field',
               default='AlarmID',
               help="RT custom field to store the alarm's id."),
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
    cfg.IntOpt('reminder_update',
               default=0,
               help="Seconds since ticket's last update."),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="request_tracker")


class RequestTracker(object):
    def __init__(self):
        self.conn  = self._connect()
        self.cache = []
        
        self.load_cache()


    def _connect(self):
        return RTResource('%s/REST/1.0/' % CONF.request_tracker.url,
                          CONF.request_tracker.username, 
                          CONF.request_tracker.password, 
                          CookieAuthenticator)
  

    def _find(self, alarm_id):
        """Searches for a ticket that contains the <alarm_id> in the custom
           field specified in configuration.

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


    def get_ticket(self, ticket_id=None):
        if ticket_id:
            logger.debug("Retrieving ticket %s data" % ticket_id)
            return [dict(self.conn.get(path="ticket/%s" % ticket_id).parsed[0])]
        else:
            logger.debug("Retrieving ALL ticket's data")
            response = self.conn.get(path=("search/ticket?query=Queue='%s'"
                                            "+AND+(Status='new'+OR+Status='"
                                            "open'+OR+Status='stalled')" 
                                            % CONF.request_tracker.queue))
            l = []
            for t in response.parsed[0]:
                id, title = t
                d = dict(self.conn.get(path="ticket/%s" % id).parsed[0])
                if d['CF.{%s}' % CONF.request_tracker.alarm_custom_field]:
                    l.append(d)
            return l


    def set_status(self, ticket_id, status):
        """Sets the status of the ticket.

           <ticket_id> is a list of the tickets whose status will be updated. Has the 
                       format 'ticket/<id>'
           <status> one of the supported RT ticket status.
        """
        if not isinstance(ticket_id, list):
            raise UpdateTicketException("close function expects a list of tickets as input.")
        
        payload = { "content": {'Status': status}}
        for t_id in ticket_id:
            response = self.conn.post(path="%s/edit" % t_id, payload=payload)
            if response.status_int != 200:
                raise delato.exception.UpdateTicketException(response.status)
            logger.debug("Ticket %s set to %s status" % (t_id, status))


    def comment(self, ticket_id, **kwargs):
        """Comments a ticket.
        
           <ticket_id> has the format 'ticket/<id>'
        """
        payload = {
            "content": {
                "Action": "comment",
                "Text": Template(CONF.request_tracker.update_body).substitute(kwargs),
            }
        }
        response = self.conn.post(path="%s/comment" % ticket_id, payload=payload)
        if response.status_int != 200:
            raise delato.exception.UpdateTicketException(response.status)


    def create(self, alarm_id, **kwargs):
        """Creates a new ticket.

           <alarm_id> is an unique ID that identifies the alarm, so that
                      this alarm are only mapped to one ticket.
           KWARGS     must contain the keys being used in the templates.
        """
        kwargs.update({"alarm_id": alarm_id})
        logger.debug("Keyword arguments: %s" % kwargs)
        try:
            payload = {
                "content": {
                    "Queue"  : CONF.request_tracker.queue,
                    "Subject": Template(CONF.request_tracker.new_subject).substitute(kwargs),
                    "Text"   : Template(CONF.request_tracker.new_body).substitute(kwargs),
                }
            }
        except KeyError, e:
            raise delato.exception.MissingTemplateArgument(str(e))

        if CONF.request_tracker.alarm_custom_field: 
            payload["content"]["CF-%s" % CONF.request_tracker.alarm_custom_field] = alarm_id
       
        logger.debug("Ticket content: %s" % payload["content"])
        if not self._find(alarm_id):
            logging.info("Creating ticket for alarm ID: %s" % alarm_id)
            try:
                response = self.conn.post(path='ticket/new', payload=payload,)
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


    def load_cache(self):
        """Stores the open tickets in memory.

           Just stores the ones with the custom field set.
        """
        self.cache = self.get_ticket()
        logger.debug("Cache content: %s" % self.cache)

