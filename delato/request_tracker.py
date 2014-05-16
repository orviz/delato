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
    cfg.BoolOpt('noop',
               default=False,
               help="Do not execute POST operations."),
    cfg.IntOpt('cache_expiration',
               default=600,
               help="Expiration period (in seconds) to refresh the ticket cache."),
    cfg.BoolOpt('reopen_rejected',
               default=True,
               help="Reopens a ticket in case it has been already rejected."),
]

CONF = cfg.CONF
CONF.register_opts(opts, group="request_tracker")


class RequestTracker(object):
    def __init__(self):
        self.conn  = self._connect()
        self.cache_data = []
        self.cache_timestamp = 0
        self.custom_field = CONF.request_tracker.alarm_custom_field
        
        if CONF.request_tracker.noop:
            logger.info(("Requested noop option. Will not execute POST "
                         "(create, edit, ..) operations."))
        if CONF.request_tracker.reopen_rejected:
            logger.debug(("Reopen rejected tickets in case the same alarm "
                          "ID is re-triggered."))
            

    def _connect(self):
        return RTResource('%s/REST/1.0/' % CONF.request_tracker.url,
                          CONF.request_tracker.username, 
                          CONF.request_tracker.password, 
                          CookieAuthenticator)

    
    def get_ticket(self, ticket_id):
        """Gets the ticket data for the given ID.
           
           <ticket_id> is a string with the form 'ticket/<id>'.
        """
        response = self.conn.get(path="%s" % ticket_id)
        if response.status_int != 200:
            raise delato.exception.GetTicketException(response.status)
        return dict(response.parsed[0])


    def search(self, status):
        """Searches for tickets that are in the given status."""
        status_cond = "+OR+".join(["Status='%s'" % st for st in status])
        response = self.conn.get(path=("search/ticket?query=Queue='%s'"
                                       "+AND+(%s)+AND+'CF.{%s}'LIKE'%%'"
                                       % (CONF.request_tracker.queue,
                                          status_cond,
                                          self.custom_field)))
        l = []
        try:
            for t in response.parsed[0]:
                id, title = t
                l.append(self.get_ticket("ticket/%s" % id))
        except IndexError:
            pass

        return l

    def load_cache(self):
        """Return the open tickets managed by delato.

           It relies on a cache mechanism which is updated whenever 
           the given expiration time is reached.
        """
        status = ["new", "open", "stalled"]
        last_update_seconds = time.time()-self.cache_timestamp
        if last_update_seconds > CONF.request_tracker.cache_expiration:
            self.cache_data = self.search(status)
            self.cache_timestamp = time.time()
            logger.debug(("Cache preservation (%s) exceeded by %.2f "
                          "seconds. Cache updated." 
                          % (CONF.request_tracker.cache_expiration,
                             last_update_seconds)))
        
        logger.debug("CACHE entries: %s" % len(self.cache_data))
        logger.debug("CACHE content: %s" % self.cache_data)
        
        return self.cache_data


    # Cache property
    cache = property(load_cache)

    def set_status(self, ticket_id, status):
        """Sets the status of the ticket.

           <ticket_id> is a list of the tickets whose status will be updated. Has the 
                       format 'ticket/<id>'
           <status> one of the supported RT ticket status.
        """
        if not isinstance(ticket_id, list):
            raise delato.exception.UpdateTicketException(("close function expects a "
                                                         "list of tickets as input."))
        
        payload = { "content": {'Status': status}}
        for t_id in ticket_id:
            if not CONF.request_tracker.noop:
                response = self.conn.post(path="%s/edit" % t_id, payload=payload)
                if response.status_int != 200:
                    raise delato.exception.UpdateTicketException(response.status)
            logger.debug("Ticket '%s' set to %s status" % (t_id, status))


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
        if not CONF.request_tracker.noop:
            response = self.conn.post(path="%s/comment" % ticket_id, payload=payload)
            if response.status_int != 200:
                raise delato.exception.UpdateTicketException(response.status)


    def create(self, alarm_id, **kwargs):
        """Creates a new ticket.

           <alarm_id> is an unique ID that identifies the alarm, so that
                      this alarm are only mapped to one ticket.
           KWARGS     must contain the keys being used in the templates.
        """
        if CONF.request_tracker.reopen_rejected:
            l = [d for d in self.search(status=["rejected"]) 
                   if d["CF.{%s}" % self.custom_field] == alarm_id]
            if l:
                logger.debug(("Found a ticket '%s' in rejected status with "
                              "the same alarm ID %s associated."
                              % (l[0]["id"], alarm_id)))
                self.set_status([l[0]["id"]], "open")
                return  

        logger.debug("Creating ticket for alarm %s" % alarm_id)
        kwargs.update({"alarm_id": alarm_id})
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

        payload["content"]["CF-%s" % self.custom_field] = alarm_id
        logger.debug("Ticket content: %s" % payload["content"])
        
        if not CONF.request_tracker.noop:
            try:
                response = self.conn.post(path='ticket/new', payload=payload,)
                logger.debug("Ticket parsed: %s" % response.parsed)
                logger.debug("Ticket status: %s" % response.status)
                if response.status_int != 200:
                    raise delato.exception.CreateTicketException(response.status)
                ticket_id = response.parsed[0][0][1]
                ticket_no = ticket_id.split("/")[1]
                logger.info("Ticket %s (alarm %s) has been successfully created" 
                             % (ticket_no, alarm_id))
                self.cache_data.append(self.get_ticket(ticket_id))
                logger.debug("CACHE updated with the recently created ticket %s" 
                              % ticket_no)
            except RTResourceError as e:
                logger.error(e.response.status_int)
                logger.error(e.response.status)
                logger.error(e.response.parsed)
