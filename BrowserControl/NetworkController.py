import logging
import os

import dns
# noinspection PyPackageRequirements
import speedtest
from browsermobproxy import Server
from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait

from BrowserControl.MitmServer import MitMServer

LOGGING_LEVEL = logging.DEBUG

handler = logging.StreamHandler()
handler.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
logger.addHandler(handler)


class NetworkControllerChrome:
    proxy_keys = ['httpProxy', 'httpsProxy']

    def __init__(self, browser_driver='chrome/chromedriver_75'):
        self.browser_driver = browser_driver
        self.browser = None
        self.proxy_server_port = None
        self.proxy_server = None
        self.proxy = None
        self.proxy_param = None

    def test_speed(self):
        s = speedtest.Speedtest()
        s.get_servers()
        s.get_best_server()
        s.download()
        s.upload()
        res = s.results.dict()
        return res["download"] * 1e-6, res["upload"] * 1e-6, res["ping"]

    def create_proxy(self, params=None):
        if params is not None:
            for key in self.proxy_keys:
                proxy_adress = params[key]
                ip_adress = ':'.join(proxy_adress.split(':')[:-1])
                if not ip_adress.replace('.', '').isdigit():
                    # Need to resolve the host
                    host_adress = ip_adress.split('//')[1]
                    for rdata in dns.resolver.query(host_adress):
                        ip_adress = rdata
                    params[key] = str(ip_adress) + ':' + str(proxy_adress.split(':')[-1])
        self.proxy_param = params
        logger.debug('Created Proxy with %s' % (str(params)))
        return self.proxy_server.create_proxy(params=params)

    def create_har(self, proxy_config='Default'):
        if proxy_config == 'Default':
            proxy_config = {'captureHeaders': True, 'captureContent': False}
        self.proxy.new_har(options=proxy_config)

    """
    https://intoli.com/blog/clear-the-chrome-browser-cache/
    """

    @staticmethod
    def get_clear_browsing_button(driver):
        """Find the "CLEAR BROWSING BUTTON" on the Chrome settings page."""
        return driver.find_element_by_css_selector('* /deep/ #clearBrowsingDataConfirm')

    def clear_cache(self, timeout=60):

        """Clear the cookies and cache for the ChromeDriver instance."""
        # navigate to the settings page
        self.browser.get('chrome://settings/clearBrowserData')

        # wait for the button to appear
        wait = WebDriverWait(self.browser, timeout)
        wait.until(self.get_clear_browsing_button)

        # click the button to clear the cache
        self.get_clear_browsing_button(self.browser).click()

        # wait for the button to be gone before returning
        wait.until_not(self.get_clear_browsing_button)
        self.browser.delete_all_cookies()
        self.browser.execute_script('window.localStorage.clear()')
        self.browser.execute_script('window.sessionStorage.clear()')

    def reset_browsermob_proxy(self):
        if self.proxy is not None:
            self.proxy.close()

    def obtain_har_browsermob(self):
        if self.proxy is None:
            raise NameError('No Proxy initialized')
        return self.proxy.har['log']['entries']

    def start_browsermob_server(self, browsermob_server_path='browsermob-proxy-2.1.4/bin/browsermob-proxy', port=8080):
        logging.info('Starting Browsermob Server with %d' % port)
        self.proxy_server_port = port
        self.proxy_server = Server(browsermob_server_path, options={'port': port})
        self.proxy_server.start()

    def stop_browsermob_server(self):
        if self.proxy_server is not None:
            self.reset_browsermob_proxy()
            self.proxy_server.stop()
        os.system('pkill --signal 9 -f name=browsermob-proxy')

    def stop_mitm_server(self):
        os.system('pkill --signal 9 -f name=mitmdump')

    def start_mitm_proxy(self, mitmproxy_server_path='ABRAnalyzer/Libraries/mitmproxy-4.0.4-linux/mitmdump', port=8080):
        self.proxy_server_port = port
        self.proxy_server = MitMServer(mitmproxy_server_path, options={'port': port})
        return self.proxy_server


class NetworkControllerFirefox(NetworkControllerChrome):
    def start_browser(self, add_options=[]):
        options = webdriver.FirefoxOptions()
        options.add_argument('--disable-application-cache')
        if self.proxy is not None:
            options.add_argument('--proxy-server=%s' % str(self.proxy.proxy))
        logger.debug('Creating Browser with %s' % str(options.arguments))
        self.browser = webdriver.Firefox(executable_path=self.browser_driver, firefox_options=options)
