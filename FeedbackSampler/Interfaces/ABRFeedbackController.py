from abc import ABC, abstractmethod

from selenium.webdriver.chrome.webdriver import WebDriver


class ABRFeedbackController(ABC):

    def __init__(self):
        pass

    def specific_options_browser(self):
        return []


    def is_well_formed(self,url):
        return True

    def obtain_byte_start(self,media_request):
        return 0

    def obtain_byte_end(self,media_request):
        return 0

    def map_video_url(self,url):
        return url

    @abstractmethod
    def extract_video_id(self,video_url):
        pass

    @abstractmethod
    def init_controls(self, browser: WebDriver):
        """
        Is called when we start sampling. Should  prepare the call to any other function
        :param browser:
        :return:
        """
        print('Not-Implemented')

        pass

    @abstractmethod
    def play(self):
        """
        Function which should start the video
        :return:
        """
        print('Not-Implemented')

        pass

    def skip_add(self):
        pass

    @abstractmethod
    def is_playing(self):
        """
                Function which should check whether the video is playing
                :return:
                """
        print('Not-Implemented')

        pass

    @abstractmethod
    def fullscreen(self):
        """
        Putting the video in fullscreen
        :return:
        """
        print('Not-Implemented')
        pass

    @abstractmethod
    def filter_media_requests(self,har_file):
        return True

    @abstractmethod
    def obtain_segment_identifier(self, url):
        return True

    def volume_control(self, intensity: float):
        """
        Sets the volume [0,100] to the percentage of the max volumes
        :param intensity:
        :return:
        """
        print('Not-Implemented')
        pass
