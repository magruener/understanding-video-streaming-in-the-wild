from appium import webdriver
import argparse
from selenium.webdriver.common.action_chains import ActionChains
import os
import subprocess
import sys
from selenium.webdriver.common.keys import Keys
import time
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
import json
import datetime



# VIMEO APP ELEMENTS ID
PLAY_PAUSE_BUTTON = 'com.vimeo.android.videoapp:id/view_video_controller_play_pause_imagebutton'
SKIP_ID = 'com.vimeo.android.videoapp:id/activity_welcome_skip_textview'
SEARCH = 'com.vimeo.android.videoapp:id/floating_action_button'
SEARCH_TEXT_FIELD = 'com.vimeo.android.videoapp:id/search_src_text'
VIDEO_CLASS_ELEMENTS = 'android.widget.RelativeLayout'
SEARCH_TEXT_CLASS = 'android.widget.EditText'
FULL_SCREEN_ID =  'com.vimeo.android.videoapp:id/view_video_controller_fullscreen_imagebutton'
TOUCH_CONTROLLER = 'com.vimeo.android.videoapp:id/view_video_player_touch_controller'


# KEY VALUES
WAIT = 10
ENTER_KEY = 66
SPACE_KEY = 62


PATH = lambda p: os.path.abspath(
    os.path.join(os.path.dirname(__file__), p)
)




def init():
	
	desired_caps = {}
	desired_caps['platformName'] = 'Android'
	desired_caps['platformVersion'] = '6.0'
	desired_caps['automationName'] = 'uiautomator2'
	desired_caps['deviceName'] = 'Android Emulator'
	desired_caps['app'] = PATH('./resources/com.vimeo.android.videoapp.apk')
	desired_caps['newCommandTimeout'] = 1200

	driver = webdriver.Remote('http://localhost:4723/wd/hub', desired_caps)
	return driver	

def find_element_and_click(driver, element):
	
	el = None
	try:
		wait = WebDriverWait(driver, WAIT)
		el = wait.until(EC.element_to_be_clickable((By.ID,element)))
	
 	except TimeoutException as e:
		print(e)
		return False

	el.click()
	return True
	

def type(driver, element, video_id_search):
	
	text_field = None
	try:
		wait = WebDriverWait(driver, WAIT)
		search_bar = wait.until(EC.element_to_be_clickable((By.CLASS_NAME,element)))
	
 	except TimeoutException as e:
		print(e)
		return False


	search_bar.send_keys(video_id_search)
 	driver.press_keycode(ENTER_KEY)
	return True	
	
def click_on_first_video(driver, ELEMENT_ID):
	el = None
	
	Video_Panel_Ready = False
	
	while not Video_Panel_Ready:
		try:
			driver.implicitly_wait(WAIT)
			el = driver.find_elements(By.CLASS_NAME, ELEMENT_ID)[3]
			Video_Panel_Ready = True

 		except TimeoutException as e:
			print(e)
			return False
		except Exception as e:
			continue

	el.click()
	return True
	


def search_and_click(driver, VIDEO_SEARCH_KEY, video_info):
	if not find_element_and_click(driver, SKIP_ID) \
                or not find_element_and_click(driver, SEARCH) \
                or not type(driver, SEARCH_TEXT_CLASS, VIDEO_SEARCH_KEY) \
                or not click_on_first_video(driver, VIDEO_CLASS_ELEMENTS) \
                or not go_full_screen(driver, video_info):
		
                return False
	
	return True



def go_full_screen(driver, info_file):
	el = None

	Video_FullScreen_Ready = False
	
	while not Video_FullScreen_Ready:
		try:
			driver.press_keycode(SPACE_KEY)
		
			time.sleep(1)		
			wait = WebDriverWait(driver, WAIT)
			el = wait.until(EC.presence_of_element_located((By.ID, FULL_SCREEN_ID)))
			Video_FullScreen_Ready = True
	
 		except Exception as e:
			print(e)
			continue
					
	
	el.click()
 	time.sleep(1)
	driver.press_keycode(SPACE_KEY)
	start_of_playback = datetime.datetime.now()
	
	with open(info_file, "r") as fin:
		datas = json.load(fin)
	
	datas["PlaybackStart"] = str(start_of_playback)
	
	with open(info_file, "w") as fout:
		json.dump(datas, fout)
	
	return True
	


def check_if_playing(driver):
	try:
		el = driver.find_element(By.ID, PLAY_PAUSE_BUTTON)
		return False
	except:
		return True




if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='GET parameters necessary to launch a video in Selenium')
	parser.add_argument('--video_key_search', dest='key_search', required=True)
	parser.add_argument('--video_info', dest='video_info_file', required=True)
	args = parser.parse_args()
	driver = init()
	if search_and_click(driver, args.key_search, args.video_info_file):
		time.sleep(10)
		if check_if_playing(driver):
			print("Success")
			sys.exit(0)

	print("Something went wrong")
	sys.exit(-1)

	
