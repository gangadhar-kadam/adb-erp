# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
import webnotes

from webnotes.utils import load_json, nowdate, cstr
from webnotes.model.code import get_obj
from webnotes.model.doc import Document
from webnotes import msgprint
from webnotes.model.bean import getlist, copy_doclist

sql = webnotes.conn.sql
	
class DocType:
	def __init__(self, doc, doclist=[]):
		self.doc = doc
		self.doclist = doclist

	def validate_receiver_nos(self,receiver_list):
		validated_receiver_list = []
		i=1
		for d in receiver_list:
                        while i<len(receiver_list):
                          a=cstr(d).split('-')
                          #msgprint(a[1])
                          i=i+1
                          validated_receiver_list.append(a[1])

			'''
			# remove invalid character
			invalid_char_list = [' ', '+', '-', '(', ')']
			for x in invalid_char_list:
				d = d.replace(x, '')
				
			validated_receiver_list.append(d)
			'''
		if not validated_receiver_list:
			msgprint("Please enter valid mobile nos", raise_exception=1)

		return validated_receiver_list


	def get_sender_name(self):
		"returns name as SMS sender"
		sender_name = webnotes.conn.get_value('Global Defaults', None, 'sms_sender_name') or \
			'ERPNXT'
		if len(sender_name) > 6 and \
				webnotes.conn.get_value("Control Panel", None, "country") == "India":
			msgprint("""
				As per TRAI rule, sender name must be exactly 6 characters.
				Kindly change sender name in Setup --> Global Defaults.
				
				Note: Hyphen, space, numeric digit, special characters are not allowed.
			""", raise_exception=1)
		return sender_name
	
	def get_contact_number(self, arg):
		"returns mobile number of the contact"
		args = load_json(arg)
		number = sql("""select mobile_no, phone from tabContact where name=%s and %s=%s""" % 
			('%s', args['key'], '%s'), (args['contact_name'], args['value']))
		return number and (number[0][0] or number[0][1]) or ''
	
	def send_form_sms(self, arg):
		"called from client side"
		args = load_json(arg)
		self.send_sms([str(args['number'])], str(args['message']))

	def send_sms(self, receiver_list, msg, sender_name = ''):
		receiver_list = self.validate_receiver_nos(receiver_list)

		arg = {
			'receiver_list' : receiver_list,
			'message'		: msg,
			'sender_name'	: sender_name or self.get_sender_name()
		}

		if webnotes.conn.get_value('SMS Settings', None, 'sms_gateway_url'):
			ret = self.send_via_gateway(arg)
			msgprint(ret)

	def send_via_gateway(self, arg):
		ss = get_obj('SMS Settings', 'SMS Settings', with_children=1)
		args = {ss.doc.message_parameter : arg.get('message')}
		for d in getlist(ss.doclist, 'static_parameter_details'):
			args[d.parameter] = d.value
		
		resp = []
		for d in arg.get('receiver_list'):
			args[ss.doc.receiver_parameter] = d
			resp.append(self.send_request(ss.doc.sms_gateway_url, args))

		return resp

	# Send Request
	# =========================================================
	def send_request(self, gateway_url, args):
		import httplib, urllib
		server, api_url = self.scrub_gateway_url(gateway_url)
		conn = httplib.HTTPConnection(server)  # open connection
		headers = {}
		headers['Accept'] = "text/plain, text/html, */*"
		conn.request('GET', api_url + urllib.urlencode(args), headers = headers)    # send request
		resp = conn.getresponse()     # get response
		resp = resp.read()
		return resp

	# Split gateway url to server and api url
	# =========================================================
	def scrub_gateway_url(self, url):
		url = url.replace('http://', '').strip().split('/')
		server = url.pop(0)
		api_url = '/' + '/'.join(url)
		if not api_url.endswith('?'):
			api_url += '?'
		return server, api_url


	# Create SMS Log
	# =========================================================
	def create_sms_log(self, arg, sent_sms):
		sl = Document('SMS Log')
		sl.sender_name = arg['sender_name']
		sl.sent_on = nowdate()
		sl.receiver_list = cstr(arg['receiver_list'])
		sl.message = arg['message']
		sl.no_of_requested_sms = len(arg['receiver_list'])
		sl.no_of_sent_sms = sent_sms
		sl.save(new=1)
