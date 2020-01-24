import logging
from abc import ABC

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from FeedbackSampler.Implementations.ChunkBasedFeedbackController import ChunkBasedFeedbackController

LOGGING_LEVEL = logging.INFO

handler = logging.StreamHandler()
handler.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
logger.addHandler(handler)


class ContinousFeedbackController(ChunkBasedFeedbackController, ABC):
    pass


class FacebookFeedbackController(ContinousFeedbackController):

    def extract_video_id(self, video_url):
        video_id = ''
        idx = 1
        while len(video_id) == 0:
            video_id = video_url.split('/')[-idx]
            idx += 1
        return video_id

    def obtain_byte_start(self, media_request):
        query_string = {v.split('=')[0]: v.split('=')[1] for v in media_request[
            'request']['url'].split('?')[-1].split('&')}
        return float(query_string['bytestart'])

    def obtain_byte_end(self, media_request):
        query_string = {v.split('=')[0]: v.split('=')[1] for v in media_request[
            'request']['url'].split('?')[-1].split('&')}
        return float(query_string['byteend'])

    def fullscreen(self):
        screen_button = self.browser.find_element_by_css_selector('button[data-testid="fullscreen_control"]')
        screen_button.click()


    def obtain_segment_identifier(self, media_request_url):
        query_string = {v.split('=')[0]: v.split('=')[1] for v in media_request_url.split('?')[-1].split('&')}
        assert 'oh' in query_string, 'Wrongly formatted %s' % query_string
        segment_id = 'oh:{oh}_range:{range}'.format(oh=query_string[
            'oh'], range=query_string['bytestart'] + '-' + query_string['byteend'])
        return segment_id


class YoutubeFeedbackController(ContinousFeedbackController):

    #def get_local_client_state(self):
    #    return self.browser.execute_script('return getLastState();')

    def extract_video_id(self, video_url):
        video_id = video_url.split('=')[-1]
        return video_id

    def __init__(self, sampling_freq=0.5, max_retry=70, t_s_min_played=5):
        super().__init__()
        self.sampling_freq = sampling_freq
        self.max_retry = max_retry
        self.t_s_min_played = t_s_min_played

    def is_playing(self):
        return not bool(self.browser.execute_script('return player.paused;'))

    def obtain_byte_start(self, media_request):
        query_string = {v.split('=')[0]: v.split('=')[1] for v in media_request[
            'request']['url'].split('?')[-1].split('&')}
        return float(query_string['range'].split('-')[0])

    def obtain_byte_end(self, media_request):
        query_string = {v.split('=')[0]: v.split('=')[1] for v in media_request[
            'request']['url'].split('?')[-1].split('&')}
        return float(query_string['range'].split('-')[1])

    def obtain_segment_identifier(self, media_request_url):
        query_string = {v.split('=')[0]: v.split('=')[1] for v in media_request_url.split('?')[-1].split('&')}
        assert 'itag' in query_string, 'Wrongly formatted %s' % query_string
        segment_id = 'itag:{itag}_range:{range}'.format(itag=query_string[
            'itag'], range=query_string['range'])
        return segment_id

    def is_well_formed(self, url):
        try :
            query_string = {v.split('=')[0]: v.split('=')[1] for v in url.split('?')[-1].split('&')}
            well_formed = 'itag' in query_string
            return well_formed
        except:
            return False

    def ad_playing(self):
        return 1 == int(self.browser.execute_script(
            "return VideoPlayer.getAdState()"))

    def play(self):
        self.browser.execute_script(
            "VideoPlayer.playVideo()")

    def stop(self):
        self.browser.execute_script(
            "VideoPlayer.stopVideo()")

    def fullscreen(self):
        screen_button = self.browser.find_element_by_css_selector('button.ytp-fullscreen-button.ytp-button')
        screen_button.click()

    def volume_control(self, intensity):
        self.browser.execute_script(
            "VideoPlayer.setVolume(%d)" % (intensity * 100))

    def skip_add(self):
        try:
            logger.debug('Trying to press skip button')
            bt = self.browser.find_element_by_css_selector('button[class="ytp-ad-skip-button ytp-button"]')
            bt.click()
        except WebDriverException:
            pass


    def init_controls(self, browser):
        self.browser = browser
        element = WebDriverWait(browser, self.timeout).until(
            expected_conditions.presence_of_element_located(
                (By.ID, "movie_player")))
        YouTubeSamplerCode = ''
        with open('FeedbackSampler/YouTubeSampler.js','r') as YouTubeSampler:
            YouTubeSamplerCode = YouTubeSampler.read()
        self.browser.execute_script(YouTubeSamplerCode)
        self.volume_control(0.0)
        self.play()