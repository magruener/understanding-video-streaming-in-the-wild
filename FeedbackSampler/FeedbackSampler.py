import json
import logging
import os
import threading
import time

import blist
import pandas as pd
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait

from FeedbackSampler.Implementations.ChunkBasedFeedbackController import ChunkBasedFeedbackController
from TrafficController.TCFeedbackControllerChunk import TCFeedbackControllerChunk

MAX_WAITING_TIME_S = 60
TIMEOUT = 60
BROWSER_TIMEOUT_S = 0.25
MAX_STREAMING_TIME_FACTOR = 5  # Hard limit of 5 times the original video length
MAX_STREAMING_TIME_S = 1200

LOGGING_LEVEL = logging.DEBUG

handler = logging.StreamHandler()
handler.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
logger.addHandler(handler)


class FeedbackSampler:
    """
    Utility function which describes one experiment
    """

    def __init__(self,
                 browser_proxy,
                 TC_Feedback_Controller: TCFeedbackControllerChunk,
                 ABR_Feedback_Controller: ChunkBasedFeedbackController,
                 browser_driver,
                 sampling_rate=0.5,
                 video_url=None,
                 result_path=None,
                 logging_level=logging.INFO,
                 DEBUG_MODE=False,
                 add_adblocker=True,
                 add_measurement_at_client=False):
        """

        :param browser_proxy:
        :param TC_Feedback_Controller:
        :param ABR_Feedback_Controller:
        :param browser_driver:
        :param sampling_rate:
        :param video_url:
        :param result_path:
        :param logging_level:
        :param DEBUG_MODE:
        :param add_adblocker:
        :param add_measurement_at_client:
        """

        self.add_measurement_at_client = add_measurement_at_client
        self.add_adblocker = add_adblocker
        self.browser_driver = browser_driver
        self.ABR_Feedback_Controller = ABR_Feedback_Controller
        self.DEBUG_MODE = DEBUG_MODE
        self.browser_proxy = browser_proxy
        self.TC_Feedback_Controller = TC_Feedback_Controller
        self.video_url = video_url
        self.video_url = self.ABR_Feedback_Controller.map_video_url(self.video_url)

        self.sampling_rate = sampling_rate
        self.result_path = result_path
        self.trace = TC_Feedback_Controller.name
        self.length_videos_s = int(TC_Feedback_Controller.video_information_csv.seg_len_s.sum())
        self.log_client = True
        TC_Feedback_Controller.set_parent_logging_path(result_path)

        handler = logging.StreamHandler()
        handler.setLevel(logging_level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger = logging.getLogger(self.trace)
        self.logger.setLevel(logging_level)
        self.logger.addHandler(handler)
        self.logger.info('Initialized Experiment')
        self.local_client_state_arr = []

        self.small_chunk = ['https://vod-metro.twitch.tv/f0b3badd0d2ed73df98d_dota2ti_92752695933_9086259125/160p30/562.ts']
        self.small_chunk += ['https://arteptweb-vh.akamaihd.net/i/am/ptweb/072000/072400/072427-001-B_0_VOA-STE%5BANG%5D_AMM-PTWEB_XQ.qaaZ16lOD7.smil/segment19_3_av.ts']
        self.medium_chunk = ['https://vod-secure.twitch.tv/f0b3badd0d2ed73df98d_dota2ti_92752695933_9086259125/480p30/568.ts']
        self.medium_chunk += ['https://arteptweb-vh.akamaihd.net/i/am/ptweb/081000/081000/081018-001-A_0_VOA-STE%5BANG%5D_AMM-PTWEB_XQ.10KiUtIo2f.smil/segment5_0_av.ts']
        self.large_chunk = ['https://vod-metro.twitch.tv/f0b3badd0d2ed73df98d_dota2ti_92752695933_9086259125/720p60/573.ts']

    def get_clear_browsing_button(self, driver):
        """Find the "CLEAR BROWSING BUTTON" on the Chrome settings page."""
        return driver.find_element_by_css_selector('* /deep/ #clearBrowsingDataConfirm')

    def clear_cache(self, driver, timeout=60):
        """Clear the cookies and cache for the ChromeDriver instance."""
        # navigate to the settings page
        driver.get('chrome://settings/clearBrowserData')

        # wait for the button to appear
        wait = WebDriverWait(driver, timeout)
        wait.until(self.get_clear_browsing_button)

        # click the button to clear the cache
        self.get_clear_browsing_button(driver).click()

        # wait for the button to be gone before returning
        wait.until_not(self.get_clear_browsing_button)

    def start_browser(self, add_options=None):
        if add_options is None:
            add_options = []
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--disable-application-cache')
        chrome_options.add_argument('--ignore-ssl-errors=yes')
        chrome_options.add_argument('--ignore-certificate-errors')
        for option in add_options:
            chrome_options.add_argument(option)
        if self.browser_proxy is not None:
            chrome_options.add_argument('--proxy-server=%s' % str(self.browser_proxy.proxy))
        if self.add_adblocker:
            chrome_options.add_extension('Libraries/AdBlock_YouTube.crx')  # Might need to be adapted
        logger.info('Creating Browser with %s' % str(chrome_options.arguments))

        browser = webdriver.Chrome(executable_path=self.browser_driver, chrome_options=chrome_options)
        return browser

    def client_logger_function(self):
        while self.log_client:
            try:
                local_client_state = self.ABR_Feedback_Controller.get_local_client_state()
                if -1 not in local_client_state :
                    self.local_client_state_arr.append(local_client_state)
            except TimeoutError:
                print('Had to wait too long')
            time.sleep(0.1)

    def curl_bw_cmd(self,url_idx):
        curl_stat_cmd = "curl %s -o /dev/null --insecure "
        curl_stat_cmd = curl_stat_cmd % self.medium_chunk[url_idx % len(self.medium_chunk)]
        if self.browser_proxy is not None:
            curl_stat_cmd += ' -x %s' % str(self.browser_proxy.proxy)
        curl_stat_cmd += " -w '%{time_total},%{size_download},%{speed_download}'"
        return curl_stat_cmd

    def curl_latency_cmd(self,url_idx):
        curl_stat_cmd = "curl %s -o /dev/null --range 0-300000 --insecure "
        curl_stat_cmd = curl_stat_cmd % self.medium_chunk[url_idx % len(self.medium_chunk)]
        if self.browser_proxy is not None:
            curl_stat_cmd += ' -x %s' % str(self.browser_proxy.proxy)
        curl_stat_cmd += " -w '%{time_total},%{size_download},%{speed_download}'"
        return curl_stat_cmd

    def measure_bw_with_curl(self,url_idx):
        curl_stat_cmd = self.curl_bw_cmd(url_idx)
        try:
            curl_response_str = os.popen(curl_stat_cmd).read()
            time_s, response_byte, byte_s = curl_response_str.split(',')
            return float(response_byte), float(time_s), (float(byte_s) * 8e-6)
        except:
            return 0, 0, 0

    def measure_latency_with_curl(self,url_idx):
        curl_stat_cmd = self.curl_latency_cmd(url_idx)
        try:
            curl_response_str = os.popen(curl_stat_cmd).read()
            time_s,response_byte,byte_s = curl_response_str.split(',')
            return float(response_byte),float(time_s), (float(byte_s) * 8e-6)
        except:
            return 0,0,0

    def bw_measurement_thread(self):
        url_idx = 0
        with open(self.result_path + '/local_client_bw_measurement', 'w') as bw_logging_file:
            bw_logging_file.write(self.curl_bw_cmd(url_idx) + '\n')
            bw_logging_file.write('timestamp size_packet time_elapsed mbit_estimated\n')
            while self.log_client:
                size_bytes, time_elapsed, mbit_estimated = self.measure_bw_with_curl(url_idx)
                bw_logging_file.write('{timestamp} {size_packet} {time_elapsed} {mbit_estimated}\n'.format(
                    timestamp=time.time(), size_packet=size_bytes, time_elapsed=time_elapsed,
                    mbit_estimated=mbit_estimated
                ))
                time.sleep(1.)

    def latency_measurement_thread(self):
        url_idx = 0
        with open(self.result_path + '/local_client_latency_measurement', 'w') as latency_logging_file:
            latency_logging_file.write(self.curl_latency_cmd(url_idx) + '\n')
            latency_logging_file.write('timestamp size_packet time_elapsed mbit_estimated\n')
            while self.log_client:
                size_bytes, time_elapsed, mbit_estimated = self.measure_latency_with_curl(url_idx)
                latency_logging_file.write('{timestamp} {size_packet} {time_elapsed} {mbit_estimated}\n'.format(
                    timestamp=time.time(), size_packet=size_bytes, time_elapsed=time_elapsed,
                    mbit_estimated=mbit_estimated
                ))
                time.sleep(1.)

    def start_add_measurement_at_client(self):
        ping_url = self.video_url.replace('https', 'http')
        latency_measurement = 'nohup httping -i 1 --ts --url %s ' % ping_url
        if self.browser_proxy is not None:
            latency_measurement += ' -x %s' % str(self.browser_proxy.proxy)
        latency_measurement += ' >> %s &' % (self.result_path + '/')
        with open(self.result_path + '/local_client_latency_measurement','w') as latency_file :
            latency_file.write(latency_measurement + '\n')
        self.logger.info('Starting ' + latency_measurement)
        os.system(latency_measurement)



    def start(self):
        if self.add_measurement_at_client and False: # Deprecated
            #self.start_add_measurement_at_client()
            bw_measurement_thread_instance = threading.Thread(target=self.bw_measurement_thread)
            bw_measurement_thread_instance.daemon = True
            bw_measurement_thread_instance.start()
            latency_measurement_thread_instance = threading.Thread(target=self.latency_measurement_thread)
            latency_measurement_thread_instance.daemon = True
            latency_measurement_thread_instance.start()
            print('Starting latency measurment')
        # ------------------------------ Init Buffer Datastructure
        self.TC_Feedback_Controller.stop_throttle()
        logging.info('Stopping all Throttling')

        if self.browser_proxy is not None:
            self.browser_proxy.new_har(options={'captureHeaders': True, 'captureContent': False})
            self.TC_Feedback_Controller.enable_proxy_access(self.browser_proxy)
        logging.info('Starting Browser')
        browser = self.start_browser(add_options=self.ABR_Feedback_Controller.specific_options_browser())
        # Setting Base throttle
        self.TC_Feedback_Controller.enable_browser_access(browser)
        self.TC_Feedback_Controller.prepare_throttle()
        logging.info('Sleeping to insure that the throttling is working')

        time.sleep(10)

        # ------------------------ Load the Page
        browser.set_page_load_timeout(MAX_WAITING_TIME_S)
        browser.implicitly_wait(60)
        browser.get(self.video_url)
        # Switch to the video instead of the adblock page
        if self.add_adblocker:
            browser.switch_to.window(browser.window_handles[0])
        logging.info('Wait for everything to be properly loaded')
        # ------------------------ Init the experiment
        self.ABR_Feedback_Controller.init_controls(browser=browser)
        self.ABR_Feedback_Controller.play()
        self.ABR_Feedback_Controller.fullscreen()
        self.ABR_Feedback_Controller.volume_control(0.0)
        # Start to actively throttle the whole thing
        self.TC_Feedback_Controller.init_throttle()
        current_har = None
        already_recorded_len = 0
        already_finished_index = set()
        self.local_client_state_arr = []
        client_logger_thread = threading.Thread(target=self.client_logger_function)
        client_logger_thread.daemon = True
        client_logger_thread.start()
        start_time = time.time()
        local_client_state = self.ABR_Feedback_Controller.get_local_client_state()
        self.local_client_state_arr.append(local_client_state)
        self.logger.info(
            'Started Throtteling and Acquistion %2.f s long video' % self.TC_Feedback_Controller.video_duration)
        buffered_until = 0
        played_until = 0
        browser.implicitly_wait(BROWSER_TIMEOUT_S) # Very important for YouTube otherwise we wait for ages
        try:
            while True:
                if self.ABR_Feedback_Controller.is_paused():
                    self.ABR_Feedback_Controller.play()
                local_client_state = self.local_client_state_arr[-1]

                if ((local_client_state[3] < buffered_until) and (played_until > 180)): # We have played for more than 3 minutes and then the whole thing sets back
                    break

                self.ABR_Feedback_Controller.skip_add()
                if local_client_state[3] != - 1:
                    buffered_until = local_client_state[3]
                played_until_tentative = self.ABR_Feedback_Controller.get_total_played()
                if played_until_tentative != -1:
                    played_until = played_until_tentative
                if self.browser_proxy is not None:
                    if played_until >= (self.TC_Feedback_Controller.video_duration * 0.9):
                        # We can't play till the end as it then might starts to download the next video
                        self.logger.info("We've played enough")
                        break
                    if (time.time() - start_time) >= MAX_STREAMING_TIME_S:
                        self.logger.info("Buffering took to long")
                        break
                    # --------------- Obtain the new .har
                    current_har = self.browser_proxy.har['log']['entries']
                    """
                    Browsermob updates entries in place that means for some values where there are no download times now
                    there might download times later -> we would need to ignore those indices 
                    """
                    media_requests = self.ABR_Feedback_Controller.filter_media_requests(current_har)

                    newly_downloaded = blist.sortedlist([], key=lambda parsed_entry: parsed_entry['timestamp_finish'])
                    newly_recorded = []
                    for index, media_request in enumerate(media_requests):
                        url = media_request['request']['url']
                        url = self.TC_Feedback_Controller.clean_url(url)
                        startedDateTime = pd.to_datetime(media_request['startedDateTime']).timestamp()
                        t_download_s = media_request['timings']['receive'] * 0.001
                        t_download_s = max([t_download_s,
                                            0.001])  # Sometimes the granularity of the download measurement is not enough so we set it to the lowest value
                        body_size_byte = media_request['response']['bodySize']
                        bandwidth_mbit = (body_size_byte * 8e-6) / t_download_s

                        parsed_entry = {
                            'url': media_request['request']['url'],
                            'timestamp_start': startedDateTime,
                            'timestamp_finish': startedDateTime + (float(media_request['time']) / 1000),
                            # This is wrong and should be timing - we fix this through the har in postprocessing
                            'n_segment': self.ABR_Feedback_Controller.obtain_segment_identifier(url),
                            't_download_s': t_download_s,
                            'body_size_byte': body_size_byte,
                            'bandwidth_mbit': bandwidth_mbit,
                            'byte_start': self.ABR_Feedback_Controller.obtain_byte_start(media_request),
                            'byte_end': self.ABR_Feedback_Controller.obtain_byte_end(media_request),
                        }
                        if body_size_byte != -1 and index not in already_finished_index:  # Download is finished
                            newly_downloaded.add(parsed_entry)
                            already_finished_index.add(index)
                        if index >= already_recorded_len:
                            already_recorded_len += 1
                            newly_recorded.append(parsed_entry)
                    if len(newly_recorded) > 0 or len(newly_downloaded) > 0:
                        self.TC_Feedback_Controller.update_media_requests(
                            newly_downloaded=newly_downloaded, newly_recorded=newly_recorded)
                else:
                    if played_until >= (self.TC_Feedback_Controller.video_duration * 0.95):
                        self.logger.info("We've played enough")
                        break
                    if (time.time() - start_time) >= (self.TC_Feedback_Controller.video_duration * 4):
                        self.logger.info("We have finished")
                        break
        finally:
            self.logger.info('Saving Data from Experiment')
            self.log_client = False
            self.TC_Feedback_Controller.stop_throttle()
            self.TC_Feedback_Controller.save_experiment()
            if self.add_measurement_at_client:
                os.system('pkill curl')
                bw_measurement_thread_instance.join(timeout=60)
                latency_measurement_thread_instance.join(timeout=60)
            browser.quit()
            client_logger_thread.join(timeout=60)

            if current_har is not None:
                with open(self.result_path + '/raw_har_file.json', 'w') as raw_har_file:
                    json.dump(current_har, raw_har_file)
            if len(self.local_client_state_arr) > 0:

                local_client_state_arr = pd.DataFrame(self.local_client_state_arr, columns=['timestamp_s',
                                                                                            'paused', 'played_until',
                                                                                            'buffered_until',
                                                                                            'videoWidth',
                                                                                            'videoHeight',
                                                                                            'decodedFrames',
                                                                                            'droppedFrames'])
                local_client_state_arr.to_csv(self.result_path + '/local_client_state_logger.csv')

            # ------------------------------ Stop Everything
            self.logger.debug('Stopped all Relevant Network Services')
