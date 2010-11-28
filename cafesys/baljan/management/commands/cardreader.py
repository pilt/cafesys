# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from baljan import tasks
from baljan import orders
from baljan.util import get_logger
from django.contrib.auth.models import User, Group
from django.utils.translation import ugettext as _
import os
from time import sleep

import time
#import httplib
from urllib2 import urlopen, HTTPError
from smartcard.CardMonitoring import CardMonitor, CardObserver
from smartcard.ReaderMonitoring import ReaderMonitor, ReaderObserver
from smartcard import System as scsystem
from smartcard.util import *
from smartcard.ATR import ATR

APDU_GET_CARD_ID = [0xFF, 0xCA, 0x00, 0x00, 0x00]
SELECT = [0xA0, 0xA4, 0x00, 0x00, 0x02, 0x90, 0x00]

def to_int(int_list):
	bitstring = ""
	for i in int_list:
		bitstring += bin(i)[2:]
	return int(bitstring[::-1], 2) # big endian
#	print int(bitstring, 2) #little endian

def translate_atr(atr):
	
	atr = ATR(atr)
	print atr
	print 'historical bytes: ', toHexString( atr.getHistoricalBytes() )
	print 'checksum: ', "0x%X" % atr.getChecksum()
	print 'checksum OK: ', atr.checksumOK
	print 'T0 supported: ', atr.isT0Supported()
	print 'T1 supported: ', atr.isT1Supported()
	print 'T15 supported: ', atr.isT15Supported()


#class TooFastSwipeException(Exception):
#	def __str__(self):
#		return "TooFastSwipeException: The card was swiped too fast"
#
#class rfidObserver(CardObserver):
#	def __init__(self):
#		self.cards = []
#		self.base_url = "http://localhost:8000"
#		#self.base_url = "http://google.com"
#
#	def send_order(self, uid):
#		try:
#			f = urlopen(self.base_url + "/terminal/trig-tag-shown/" + uid)
#			response = f.read()
#			if response == 'OK':
#				pass
#			elif response == 'PENDING':
#				pass
#		except HTTPError:
#			# TODO: Log error.
#			pass
#		
#		
#	def update(self, observable, (addedcards, removedcards)):
#		try:
#			for card in addedcards:
#				print "Card inserted."
#				card.connection = card.createConnection()
#				card.connection.connect()
#				response, sw1, sw2 = card.connection.transmit( APDU_GET_CARD_ID )
#				
#				if (("%.2x" % sw1) == "63"):
#					raise TooFastSwipeException
#				self.send_order(to_int(response))
#			for card in removedcards:
#				print "Card was removed."
#		except Exception, e:
#			print "Ignored error: " + str(e)
#
#
#print "This is a test"
#try:
#	
#	cardmonitor = CardMonitor()
#	cardobserver = rfidObserver()
#	cardmonitor.addObserver(cardobserver)
#except:
#	raise
#
#while 1:
#	time.sleep(100000)
#
#print "ok bye"

log = get_logger('baljan.cardreader')

# The new program.

class CardReaderError(Exception):
    pass

class StateChangeError(CardReaderError):
    pass

# There are two states: 
#   1) waiting for reader availability, and 
#   2) reading cards and putting orders
STATE_INITIAL = 0
STATE_WAITING_FOR_READER = 1
STATE_READING_CARDS = 2
STATE_EXIT = 3
STATE_NONE = 4

import struct

# XXX: Also evaluated 'i' as format, but that does not work. Unsigned ('I') is
# the way to go.
STRUCT = struct.Struct('I')
_good_size = 4
if STRUCT.size != _good_size:
    err_msg = 'size of STRUCT not %d!!!' % _good_size
    log.error(err_msg)
    raise ValueError(err_msg)


class OrderObserver(CardObserver):
    """This observer will map inserted cards to users and put a default order
    (coffee or tea) for users showing their card. Orders may or may not be
    accepted, and the user feedback is different for accepted and denied orders.
    """
    def initialize(self):
        self.clerk = orders.Clerk()

    def _put_order(self, card_id):
        orderer = User.objects.get(profile__card_id=card_id)
        preorder = orders.default_preorder(orderer)
        processed = self.clerk.process(preorder)
        if processed.accepted():
            log.info('order was accepted')
        else:
            log.info('order was not accepted')

    def _handle_added(self, cards):
        for card in cards:
            if card is None:
                log.debug('ignoring None in _handle_added')
                continue

            conn = card.createConnection()
            conn.connect()
            log.debug('connected to card')
            response, sw1, sw2 = conn.transmit(APDU_GET_CARD_ID)
            log.info('response=%r, sw1=%r, sw2=%r' % (response, sw1, sw2))
            card_id = to_id(response)
            log.info('id=%r %r' % (card_id, type(card_id)))
            self._put_order(card_id)
            conn.disconnect()
            log.debug('disconnected from card')


    def _handle_removed(self, cards):
        for card in cards:
            log.debug('removed %r' % toHexString(card.atr))

    def update(self, observable, (addedcards, removedcards)):
        card_tasks = [
            # callable             argument (cards)  description
            (self._handle_added,   addedcards,       "handle added"),
            (self._handle_removed, removedcards,     "handle removed"),
        ]
        for call, arg, desc in card_tasks:
            try:
                if len(arg):
                    call_msg = "%s (arg %r)" % (desc, arg)
                else:
                    call_msg = "%s" % desc
                ret = call(arg)
            except Exception, e:
                log.error("%s exception: %r" % (desc, e), exc_auto=True)
                tasks.play_error.delay()
            else:
                if ret is None:
                    msg = "%s finished" % desc
                else:
                    msg = "%s finished (returned %r)" % (desc, ret)
                log.debug(msg)


def to_id(card_bytes):
    buf = "".join([chr(x) for x in card_bytes])
    unpacked = STRUCT.unpack(buf)
    if len(unpacked) != 1:
        err_msg = 'unpack return more than one value!!!'
        log.error(err_msg)
        raise CardReaderError(err_msg)
    # Some returned values are of integer type, we cast to long so that the
    # return type will be the same for each card.
    return long(unpacked[0])


class Command(BaseCommand):
    args = ''
    help = 'This program puts a default order (one coffee or tea) when a card is read.'

    def _enter_state(self, state):
        states = {
            STATE_NONE: {
                'name': 'STATE_NONE',
                # no call
            },
            STATE_INITIAL: {
                'name': 'STATE_INITIAL',
                'call': self._enter_initial, 
            },
            STATE_WAITING_FOR_READER: {
                'name': 'STATE_WAITING_FOR_READER',
                'call': self._enter_waiting_for_reader, 
            },
            STATE_READING_CARDS: {
                'name': 'STATE_READING_CARDS',
                'call': self._enter_reading_cards, 
            },
            STATE_EXIT: {
                'name': 'STATE_EXIT',
                'call': self._enter_exit, 
            },
        }

        if states.has_key(state):
            state_msg = 'state change: %s -> %s' % (
                states[self.state]['name'],
                states[state]['name'],
            )
            log.info(state_msg)
        else:
            err_msg = 'bad state: %r' % state
            log.error(err_msg)
            raise StateChangeError(err_msg)

        self.state = state
        states[state]['call']()

    def _setup_card_monitor_and_observer(self):
        self.card_monitor = CardMonitor()
        log.debug('card monitor created: %r' % self.card_monitor)
        self.card_observer = OrderObserver()
        self.card_observer.initialize()
        log.debug('card observer created: %r' % self.card_observer)
        self.card_monitor.addObserver(self.card_observer)
        log.debug('card observer attached to monitor')

    def _tear_down_card_monitor_and_observer(self):
        log.debug('card observer detaching from monitor')
        if self.card_observer is not None and self.card_monitor is not None:
            self.card_monitor.deleteObserver(self.card_observer)
        self.card_monitor = None
        self.card_observer = None

    def _enter_waiting_for_reader(self):
        while len(scsystem.readers()) == 0:
            sleep(1)
        log.info('reader attached')
        self._enter_state(STATE_READING_CARDS)

    def _enter_reading_cards(self):
        self._setup_card_monitor_and_observer()
        while len(scsystem.readers()) != 0:
            log.debug('reading cards heartbeat')
            sleep(1)
        log.info('reader detached')
        self._tear_down_card_monitor_and_observer()
        self._enter_state(STATE_WAITING_FOR_READER)

    def _enter_exit(self):
        self._tear_down_card_monitor_and_observer()
        log.info('finished program, normal exit')

    def _enter_initial(self):
        initial_readers = scsystem.readers()
        log.info('connected readers: %r' % initial_readers)
        try:
            if len(initial_readers) == 0:
                initial_state = STATE_WAITING_FOR_READER
            elif len(initial_readers) == 1:
                initial_state = STATE_READING_CARDS
            else:
                err_msg = '%d readers connected' % len(initial_readers)
                raise CardReaderError(err_msg)

            self._enter_state(initial_state)
        except KeyboardInterrupt:
            log.info('user exit')
        self._enter_state(STATE_EXIT)

    def handle(self, *args, **options):
        valid = True 
        if not valid:
            raise CommandError('invalid config')

        self.card_monitor = None
        self.card_observer = None
        self.state = STATE_NONE
        self._enter_state(STATE_INITIAL)
