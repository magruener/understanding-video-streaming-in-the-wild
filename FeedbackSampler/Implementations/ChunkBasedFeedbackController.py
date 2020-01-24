import time
from abc import ABC

from selenium.common.exceptions import WebDriverException, JavascriptException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait

from FeedbackSampler.Interfaces.ABRFeedbackController import ABRFeedbackController

PING_CONTAINS = 'vod-secure.twitch.tv'


class ChunkBasedFeedbackController(ABRFeedbackController, ABC):
    """
    Creates controls for the video player (Interaction)
    """

    def __init__(self):
        super().__init__()
        self.playing = False
        self.browser = None
        self.timeout = 15

    def init_controls(self, browser):
        self.browser = browser
        element = WebDriverWait(browser, 15).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, "div video")))
        self.browser.execute_script("player = document.querySelector('div video')")
        self.volume_control(0.0)

    def is_playing(self):
        return not bool(self.browser.execute_script('return player.paused;'))

    def is_paused(self):
        return bool(self.browser.execute_script('return player.paused;'))

    def play(self):
        self.browser.execute_script("player.play()")
        """
        if self.playing:
            self.browser.execute_script(
                "player.pause()")
            self.playing = False
        else:
            self.playing = True
         """

    def volume_control(self, intensity):
        self.browser.execute_script(
            "player.volume = %.2f" % intensity)

    def filter_media_requests(self, har_file):
        filtered_har_file = []
        for entry in har_file:
            if 'video' in entry['response']['content']['mimeType'] and self.is_well_formed(entry['request']['url']):
                filtered_har_file.append(entry)
        return filtered_har_file

    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            is_progressive = '.mp4' not in url
            return is_progressive
        except:
            return False

    def get_local_client_state(self):
        paused = self.browser.execute_script('return player.paused;')
        videoWidth = self.browser.execute_script('return player.videoWidth;')
        videoHeight = self.browser.execute_script('return player.videoHeight;')
        decodedFrames = self.browser.execute_script('return player.webkitDecodedFrameCount;')
        droppedFrames = self.browser.execute_script('return player.webkitDroppedFrameCount;')
        try:
            played_until = self.browser.execute_script(
                'return player.played.end(player.played.length - 1);')
            buffered_until = self.browser.execute_script(
                'return player.buffered.end(player.buffered.length - 1);')
        except WebDriverException:
            played_until = -1
            buffered_until = -1
        return [time.time(), paused, played_until, buffered_until, videoWidth, videoHeight, decodedFrames,
                droppedFrames]

    def get_total_played(self):
        try:
            played_until = self.browser.execute_script(
                'return player.played.end(player.played.length - 1);')
        except WebDriverException:
            played_until = -1
        return played_until


class ZDFFeedbackController(ChunkBasedFeedbackController):

    def extract_video_id(self, video_url):
        video_id = video_url.split('/')[-1]
        return video_id

    def __init__(self):
        super().__init__()
        self.play_init = False

    def play(self):
        print('Pressed play')
        if self.play_button_pressed:
            self.browser.execute_script("player.play()")
        else:
            print('Pressed the big button')
            element = WebDriverWait(self.browser, 15).until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, 'button[data-title="Video abspielen"]')))
            load_player = self.browser.find_element_by_css_selector(
                'button[data-title="Video abspielen"]')
            self.browser.execute_script('document.querySelector(\'button[data-title="Video abspielen"]\').click()')
            # try:
            #    ActionChains(self.browser).move_to_element(load_player).click(load_player).perform()
            # except:
            #    load_player.click()
            self.browser.execute_script("player = document.querySelector('div video')")
            self.volume_control(0.0)
            self.play_button_pressed = True
            ct = 0
            while not self.is_playing():
                time.sleep(0.5)
                ct += 1
                if ct > 120:
                    raise TimeoutError('ZDF Player coulndt load page')
            assert self.is_playing()

    def init_controls(self, browser):
        self.browser = browser
        self.play_button_pressed = False
        try:
            self.browser.find_element_by_css_selector(
                'button[title="Zustimmen und Benachrichtigung schließen."]').click()
        except:
            print('No cookies')

    def fullscreen(self):
        buffered_until = -1
        while buffered_until == -1 :
            try:
                buffered_until = self.browser.execute_script(
                    'return player.buffered.end(player.buffered.length - 1);')
            except WebDriverException:
                buffered_until = -1
                time.sleep(1.)
        self.browser.execute_script('player.pause()')
        # self.browser.execute_script('document.querySelector(\'button[aria-label="Vollbild anzeigen"]\').click()')
        full_screen = self.browser.find_element_by_css_selector(
            'button[aria-label="Vollbild anzeigen"]')
        # ActionChains(self.browser).move_to_element(full_screen).click(full_screen).perform()
        full_screen.click()
        self.browser.execute_script('player.play()')

        # try:
        #    .click(full_screen).perform()
        # except JavascriptException:

    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            return ('.ts' in url) and (PING_CONTAINS not in url)
        except:
            return False

    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split('/')[-1].split('_')[0].replace('segment', '')) - 1


class VimeoFeedbackController(ChunkBasedFeedbackController):
    """
    Creates controls for the video player (Interaction)
    """

    def extract_video_id(self, video_url):
        video_id = video_url.split('/')[-1]
        return video_id

    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split('/')[-1].split('-')[-1].split('.')[0]) - 1

    def fullscreen(self):
        full_screen = self.browser.find_element_by_css_selector('.fullscreen')
        try:
            ActionChains(self.browser).move_to_element(full_screen).click(full_screen).perform()
        except JavascriptException:
            full_screen.click()

    def specific_options_browser(self):
        # We don't want the whole video to be contionously streamed
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        user_agent = 'user-agent={user_agent}'.format(user_agent=user_agent)
        return [user_agent]


class TwitchFeedbackController(ChunkBasedFeedbackController):

    def play(self):
        if self.is_paused():
            try:
                play_button = self.browser.find_element_by_css_selector('button[aria-label="Play (space/k)"]')
                try:
                    ActionChains(self.browser).move_to_element(play_button).click(play_button).perform()
                except:
                    play_button.click()
                return
            except:
                print("Coulnd't find the play button")
            try:
                pause_button = self.browser.find_element_by_css_selector('button[aria-label="Pause (space/k)"]')
            except:
                raise ValueError("Coulnd't find neither play nor stop button")

    def extract_video_id(self, video_url):
        video_id = video_url.split('/')[-1]
        return video_id

    def fullscreen(self):
        fullscreen = self.browser.find_element_by_css_selector('button[aria-label="Fullscreen (f)"]')
        try:
            ActionChains(self.browser).move_to_element(fullscreen).click(fullscreen).perform()
        except JavascriptException:
            fullscreen.click()

    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split('/')[-1].replace('.ts', '').split('-')[-1])

    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            is_progressive = '.mp4' not in url
            return is_progressive
        except:
            return False


class ArteFeedbackController(ChunkBasedFeedbackController):
    def init_controls(self, browser):
        self.browser = browser
        try:
            element = WebDriverWait(browser, 15).until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, "div video")))
            self.browser.execute_script("player = document.querySelector('div video')")
        except:
            element = WebDriverWait(browser, 15).until(
                expected_conditions.presence_of_element_located(
                    (By.CSS_SELECTOR, 'video[class="jw-video jw-reset"]')))
            self.browser.execute_script("player = document.querySelector('video[class=\'jw-video jw-reset\']')")
        self.volume_control(0.0)
        self.is_playing = False



    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            return ('.ts' in url) and (PING_CONTAINS not in url)
        except:
            return False

    def extract_video_id(self, video_url):
        video_id = video_url.split('/')[-3]
        return video_id

    def fullscreen(self):
        buffered_until = -1
        while buffered_until == -1:
            try:
                buffered_until = self.browser.execute_script(
                    'return player.buffered.end(player.buffered.length - 1);')
            except WebDriverException:
                buffered_until = -1
                time.sleep(1.)
        self.browser.execute_script("player.pause()")
        try:
            self.browser.execute_script("document.getElementById('footer_tc_privacy_button').click()")
        except:
            print('No Privacy Notice')
        fullscreen = self.browser.find_element_by_css_selector(
            'div.avp-icon.avp-icon-fullscreen')
        fullscreen.click()

        #ActionChains(self.browser).move_to_element(fullscreen).click(fullscreen).perform()

        #except JavascriptException:
        #
        self.browser.execute_script("player.play()")
        print('Fullscreen !!')


    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split(
            '/')[-1].split('_')[0].replace('segment', '')) - 1


class FandomFeedbackController(ChunkBasedFeedbackController):
    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            return '.ts' in url and (PING_CONTAINS not in url)
        except:
            return False

    def extract_video_id(self, video_url):
        video_id = video_url.split('/')[-2]
        return video_id

    def init_controls(self, browser):
        browser.find_element_by_css_selector(
            'div._2o0B8MF50eAK1jv60jldUQ._2c5ljMskepxxinntbmMTHJ').click()
        super().init_controls(browser)

    def fullscreen(self):
        fullscreen = self.browser.find_element_by_css_selector(
            'div.jw-icon.jw-icon-inline.jw-button-color.jw-reset.jw-icon-fullscreen')
        try:
            ActionChains(self.browser).move_to_element(fullscreen).click(fullscreen).perform()
        except JavascriptException:
            fullscreen.click()

    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split('.ts')[0].split('-')[-1]) - 1


class SRFFeedbackController(ChunkBasedFeedbackController):

    def map_video_url(self, url):
        video_url_direct = "https://player.srf.ch/p/srf/portal-detail?urn=urn:srf:video:{video_id}"
        return video_url_direct.format(video_id=url.split('=')[-1])

    def play(self):
        if self.play_button_pressed:
            self.browser.execute_script("player.play()")
        else:
            load_player = self.browser.find_element_by_css_selector(
                'div[class="srg-overlay srg-play-overlay clickable"]')
            try:
                ActionChains(self.browser).move_to_element(load_player).click(load_player).perform()
            except:
                load_player.click()
            self.browser.execute_script("player = document.querySelector('div video')")
            self.volume_control(0.0)
            self.play_button_pressed = True

    def init_controls(self, browser):
        self.browser = browser
        self.play_button_pressed = False

    def extract_video_id(self, video_url):
        video_id = video_url.split('/')[-1]
        return video_id

    def fullscreen(self):
        fullscreen = self.browser.find_element_by_css_selector(
            'div.srg-fullscreen-button.clickable')
        try:
            ActionChains(self.browser).move_to_element(fullscreen).click(fullscreen).perform()
        except JavascriptException:
            fullscreen.click()

    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split('/')[-1].split(
            '?')[0].split('_')[0].replace('segment', ''))

    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            return (PING_CONTAINS not in url)
        except:
            return False


class AOLFeedbackController(ChunkBasedFeedbackController):

    def extract_video_id(self, video_url):
        raise NotImplementedError('We currently are not using AOL')

    def init_controls(self, browser):
        self.browser = browser
        element = WebDriverWait(browser, 15).until(
            expected_conditions.presence_of_element_located(
                (By.CSS_SELECTOR, ".vdb_player")))
        self.browser.execute_script("player = vidible_players[0]")
        self.volume_control(0.0)

    def volume_control(self, intensity):
        self.browser.execute_script(
            "player.setVolume(%.2f)" % intensity)

    def is_playing(self):
        return bool(self.browser.execute_script('return player.isPlaying();'))

    def fullscreen(self):
        self.browser.execute_script("document.getElementsByClassName('fullscreen-button')[0].click()")

    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split('/')[-1].split('?')[0].split('_')[-1].replace('.ts', ''))


class TubiTVFeedbackController(ChunkBasedFeedbackController):

    def filter_media_requests(self, har_file):
        filtered_har_file = []
        for entry in har_file:
            if 'stream' in entry['response']['content']['mimeType'] and self.is_well_formed(entry['request']['url']):
                filtered_har_file.append(entry)
        return filtered_har_file

    def extract_video_id(self, video_url):
        video_id = video_url.split('/')[-1]
        return video_id

    def fullscreen(self):
        fullscreen = self.browser.find_element_by_css_selector(
            'span[id="fullscreenArea"]')
        try:
            ActionChains(self.browser).move_to_element(fullscreen).click(fullscreen).perform()
        except JavascriptException:
            fullscreen.click()

    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split('/')[-1].split('-')[-1].split('.')[0])

    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            return '.ts' in url and (PING_CONTAINS not in url)
        except:
            return False


class PornhubFeedbackController(ChunkBasedFeedbackController):

    def extract_video_id(self, video_url):
        video_id = video_url.split('=')[-1]
        return video_id

    def fullscreen(self):

        fullscreen = self.browser.find_element_by_css_selector(
            '.mhp1138_fullscreen')
        try:
            ActionChains(self.browser).move_to_element(fullscreen).click(fullscreen).perform()
        except JavascriptException:
            fullscreen.click()

    def obtain_segment_identifier(self, media_request_url):
        return int(media_request_url.split('/')[-1].split('?')[0].split('-')[1]) - 1

    def specific_options_browser(self):
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.47 Safari/537.36'
        user_agent = 'user-agent={user_agent}'.format(user_agent=user_agent)
        return [user_agent]

    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            return '.ts' in url and (PING_CONTAINS not in url)
        except:
            return False


class XVideosFeedbackController(ChunkBasedFeedbackController):

    def get_local_client_state(self):
        paused = self.browser.execute_script('return html5player.video.paused;')
        videoWidth = self.browser.execute_script('return html5player.video.videoWidth;')
        videoHeight = self.browser.execute_script('return html5player.video.videoHeight;')
        decodedFrames = self.browser.execute_script('return html5player.video.webkitDecodedFrameCount;')
        droppedFrames = self.browser.execute_script('return html5player.video.webkitDroppedFrameCount;')
        try:
            played_until = self.browser.execute_script('return html5player.video.played.end(player.played.length - 1);')
            buffered_until = self.browser.execute_script('return html5player.video.buffered.end(player.buffered.length - 1);')
        except WebDriverException:
            played_until = 0
            buffered_until = 0
        return [time.time(), paused, played_until, buffered_until, videoWidth, videoHeight, decodedFrames,
                droppedFrames]

    def extract_video_id(self, video_url):
        video_id = video_url.split('/')[-2]
        return video_id

    def play(self):
        if not self.play_button_clicked:
            play_btn = self.browser.find_element_by_css_selector('div[class="big-button play"]')
            try:
                ActionChains(self.browser).move_to_element(play_btn).click(play_btn).perform()
            except JavascriptException:
                play_btn.click()
            self.play_button_clicked = True
            self.browser.execute_script("player = document.querySelector('div video')")
            self.volume_control(0.0)
        else:
            self.browser.execute_script("html5player.play()")

    def init_controls(self, browser):
        self.browser = browser
        self.play_button_clicked = False

    def volume_control(self, intensity):
        self.browser.execute_script(
            "html5player.setVolume(%.2f)" % intensity)

    def is_playing(self):
        return bool(self.browser.execute_script('return html5player.isPlaying;'))

    def is_paused(self):
        return not bool(self.browser.execute_script('return html5player.isPlaying;'))

    def ad_playing(self, video_len_s):
        return not bool(self.browser.execute_script('return html5player.videoads === null;'))

    def fullscreen(self):
        fullscreen = self.browser.find_element_by_css_selector(
            'img[title="Fullscreen"]')
        ActionChains(self.browser).move_to_element(fullscreen).click(fullscreen).perform()

    def obtain_segment_identifier(self, media_request_url):
        url = media_request_url
        if 'hls' not in url:
            raise ValueError('Passed wrong url {url}'.format(url=url))
        return int(url.split('/')[-1].split('.ts')[0])

    def is_well_formed(self, url):
        try:
            self.obtain_segment_identifier(url)
            return ('.mp4' not in url) and (PING_CONTAINS not in url)
        except:
            return False
