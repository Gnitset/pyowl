#! /usr/bin/env python

import sys
import os
import usb.core
import usb.util
import time
import struct

try:
	from config import live_file
except ImportError:
	live_file = ".live"

class Owl(object):
	OWL_VENDOR_ID = 0x0fde
	CM160_PRODUCT_ID = 0xca05

	CP210X_IFC_ENABLE = 0x00
	CP210X_SET_BAUDRATE = 0x1E

	UART_ENABLE = 0x0001
	UART_DISABLE = 0x0000
	UART_BAUDRATE = struct.pack("<I", 250000)

	ID_MSG = [0xA9, 0x49, 0x44, 0x54, 0x43, 0x4D, 0x56, 0x30, 0x30, 0x31, 0x01]
	WAIT_MSG = [0xA9, 0x49, 0x44, 0x54, 0x57, 0x41, 0x49, 0x54, 0x50, 0x43, 0x52]

	FRAME_ID_LIVE = 0x51
	FRAME_ID_DB = 0x59

	_live = False

	def __init__(self):
		self.dev = usb.core.find(idVendor=self.OWL_VENDOR_ID, idProduct=self.CM160_PRODUCT_ID)
		if self.dev is None:
			raise ValueError('Device not found')
		try:
			self.dev.detach_kernel_driver(0)
		except:
			pass
		self.dev.set_configuration()
		cfg = self.dev.get_active_configuration()
		intf = cfg[(0,0)]
		self.epin = usb.util.find_descriptor(intf, bEndpointAddress = 0x82)
		self.epout = usb.util.find_descriptor(intf, bEndpointAddress = 0x1)
		ctHostToInterface = usb.TYPE_VENDOR | usb.RECIP_INTERFACE | usb.ENDPOINT_OUT
		self.dev.ctrl_transfer(ctHostToInterface, self.CP210X_IFC_ENABLE, self.UART_ENABLE, timeout = 500)
		self.dev.ctrl_transfer(ctHostToInterface, self.CP210X_SET_BAUDRATE, data_or_wLength = self.UART_BAUDRATE, timeout = 500)
		self.dev.ctrl_transfer(ctHostToInterface, self.CP210X_IFC_ENABLE, self.UART_DISABLE, timeout = 500)

	def io_loop(self):
		while True:
			try:
				data = self.epin.read(10000, timeout = 60*1000)
			except usb.core.USBError, err:
				if not err.errno == 110:
					raise
				print "sleeping 1s"
				time.sleep(1)
				raise
				continue
			for i in range(0, len(data), 11):
				if len(data[i:i+11]) < 11:
					break
				self.process_frame(data[i:i+11])

	def process_frame(self, frame):
		if list(frame) == self.ID_MSG:
			print "got ID_MSG"
			self.epout.write(chr(0x5A))
		elif list(frame) == self.WAIT_MSG:
			print "got WAIT_MSG"
			self.epout.write(chr(0xA5))
		else:
			if frame[0] not in (self.FRAME_ID_LIVE, self.FRAME_ID_DB):
				print "Unknown frame: %s" % frame
				return
			if sum(frame[:10]) & 0xff != frame[10]:
				print "Failed checksum: %s" % frame
			decoded_frame = self.decode_frame(frame)
			if not self._live and decoded_frame['live']:
				self._live = True
				print "Got first live frame"
			print "Frame: %(year)s-%(month)02d-%(day)02d %(hour)02d:%(min)02d %(amps)sA %(live)s - %(raw)s" % decoded_frame
			if self._live:
				open(live_file, "w+").write("%s W\n" % (float(decoded_frame['amps'])*230))

	def decode_frame(self, frame):
		ret = dict()
		ret['raw'] = str(frame)
		ret['year'] = frame[1]+2000
		ret['month'] = frame[2]
		ret['day'] = frame[3]
		ret['hour'] = frame[4]
		ret['min'] = frame[5]
		ret['amps'] = (frame[8]+(frame[9]<<8))*0.07
		if frame[0] == self.FRAME_ID_LIVE:
			ret['live'] = True
		else:
			ret['live'] = False
		return ret


if __name__ == "__main__":
	owl = Owl()
	owl.io_loop()
