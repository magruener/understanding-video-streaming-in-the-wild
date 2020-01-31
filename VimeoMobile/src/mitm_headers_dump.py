from mitmproxy import ctx
import json
import sys
import datetime as dt
from dateutil import parser
import subprocess
import os
import pgrep
import threading
from pprint import pprint
from time import sleep
from mitmproxy.script import concurrent
DIR_DATA = str(os.environ['CURRENT_EXPERIMENT'])
CURRENT_VIDEO = str(os.environ['CURRENT_VIDEO'])
MAX_SEGMENT = int(os.environ['MAX_SEGMENT'])
VIDEO_T = ['video/mp4']
BANDWIDTH_CONSTANT = 2 #Mbit/s
BITS_IN_BYTE = 8
BITS_IN_MBIT = 1000000
TIMER = 30

	
def stop_mitm():
	cmd = "killall -9 mitmdump"		
	subprocess.Popen([cmd], shell=True)
	sys.exit(0)


# Vimeo
def check_if_continue(url):
	segment_no = int(url.split('/')[-1].replace('segment-','').split('.')[0])
	video_id = url.split('/')[-6]
	if segment_no == (MAX_SEGMENT - 1) or video_id != CURRENT_VIDEO:
		print("End reached -> will start the kill timer to stop MITMDUMP")
		return True
	
	return False

def requestheaders(flow):
	flow.request.headers["started_time"] = str((dt.datetime.now() - dt.datetime(1970,1,1)).total_seconds())


def responseheaders(flow):
	old_data = {}
		
	try:
		
		if flow.response.headers['Content-Type'] not in VIDEO_T or "video" not in flow.request.url:
			flow.response.stream = True
			return
	except Exception as e:
		flow.response.stream = True
		return
	
	
	sample = {}
	try:
		sample['HeadersReceived'] = str((dt.datetime.now() - dt.datetime(1970,1,1)).total_seconds())
		sample['StartedTime'] = flow.request.headers["started_time"]
		sample['Url'] = flow.request.url
		is_video_terminated = check_if_continue(sample['Url'])
		
		if (is_video_terminated):
			threading.Timer(TIMER, stop_mitm, []).start()
			
		response_headers = [{"name": k, "value": flow.response.headers[k]} for k in flow.response.headers]
		request_headers = [{"name": k, "value": flow.request.headers[k]} for k in flow.request.headers]	
		sample['RequestHeaders'] = request_headers
		sample['ResponseHeaders'] = response_headers
		
	
	except Exception as e:
		flow.response.stream = True
		print(e)
		return
	
	
	if not os.path.exists(DIR_DATA):
		os.mkdir(DIR_DATA)
	
	filename_flow_dump = os.path.join(DIR_DATA, flow.request.url.split('/')[-1].split('.')[0])
	
	count = 1
	root_filename = filename_flow_dump
	while  os.path.exists(filename_flow_dump):
		count += 1
		filename_flow_dump = root_filename + '-' + str(count)
	
	
	new_index = len(old_data.keys())
	old_data[new_index] = sample
	
	
	def write_end_time(chunks):
		with open(filename_flow_dump, 'w') as file_write:
			for chunk in chunks:
				now = (dt.datetime.now() - dt.datetime(1970,1,1)).total_seconds()
				old_data[new_index]['EndTime'] = now
				
				file_write.seek(0)
				file_write.truncate()
				json.dump(old_data, file_write)
				yield chunk
	flow.response.stream = write_end_time	
	
	
	

	
