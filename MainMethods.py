import logging
import os
import shutil

import pandas as pd
from pyvirtualdisplay import Display
from selenium.common.exceptions import NoSuchElementException, ElementNotVisibleException, TimeoutException

from FeedbackSampler.FeedbackSampler import FeedbackSampler
from BrowserControl.NetworkController import NetworkControllerChrome
from TrafficController.TCFeedbackControllerChunk import ParsingError

SELECTED_VIDEOFRAME_CSV = 'Data/SelectedVideoDataframe.csv'
BROWSERMOB_PROXY_PATH = 'Data/Libraries/browsermob-proxy-2.1.4/bin/browsermob-proxy'
MITMPROXY_PATH = 'Data/Libraries/mitmproxy-4.0.4-linux/mitmdump'
CHROMEDRIVER_PATH = 'Data/Libraries/chromedriver_77'
VIRTUAL_DISPLAY_WIDTH = 4096
VIRTUAL_DISPLAY_HEIGHT = 3072
FIXED_RANDOM_SEED = 42
LOCAL_PASSWORD_FILE_PATH = 'pw_local' #You need the password to start TC
NETWORK_INTERFACE = 'eth0' #Which interface do you want to throttle
SITE_LOADING_STABLE_THROTTLE_MBIT = '3.' #Initial throttle in mbit
BASE_LATENCY_MS = 0 #Added latency
VIDEO_INFORMATION_PATH_TEMPLATE = 'Data/VideoInformation/{Provider}_Info/{video_id}'
RESULT_PATH_TEMPLATE = 'Data/FeedbackResults/{Provider}/{ScreenResolution}/{Model}/{ModelInstance}'

LOGGING_LEVEL = logging.DEBUG
handler = logging.StreamHandler()
handler.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
logger.addHandler(handler)



pam_files = []
for (dirpath, dirnames, filenames) in os.walk('Data/Traces/PAMTrace/'):
    pam_files.extend([os.path.join(dirpath, f) for f in filenames])
pam_files = sorted(pam_files)

with open(LOCAL_PASSWORD_FILE_PATH, 'r') as LOCAL_PASSWORD_FILE_PATH:
    LOCAL_PASSWORD_FILE_PATH = LOCAL_PASSWORD_FILE_PATH.read()

def experiment_not_finished(result_path_formatted, add_measurement_at_client=False):
    if len(os.listdir(result_path_formatted)) < 3:
        return True
    try:
        throtteling_df = result_path_formatted + '/throttle_logging.tc'
        throtteling_df = pd.read_csv(throtteling_df, sep='\t', names=['time_stamp', 'bw_mbit'])
        time_elapsed = throtteling_df.time_stamp.max() - throtteling_df.time_stamp.min()
        if time_elapsed < 120:
            return True
        local_client_state_logger = result_path_formatted + '/local_client_state_logger.csv'
        local_client_state_logger = pd.read_csv(local_client_state_logger)
        if len(local_client_state_logger) <= 3:
            return True
        if local_client_state_logger.played_until.max() < 120:
            return True
        if add_measurement_at_client:
            latency_df = pd.read_csv(result_path_formatted + '/local_client_latency_measurement', sep=' ', skiprows=1)
            bw_df = pd.read_csv(result_path_formatted + '/local_client_bw_measurement', sep=' ', skiprows=1)

    except:
        return True
    return False

def start_sampling(ABR_Feedback_Controller,
                   TC_Feedback_Controller,
                   Provider,
                   Model,
                   video_urls,
                   existing_folder_policy='replace',
                   max_modify=None,
                   use_virtual_display=True,
                   use_proxy=True,
                   add_adblocker=True,
                   add_measurement_at_client=False,
                   proxy_version='browsermob'):
    """

    :param use_proxy: Whether to use the proxy or just record the things we can sample from the video server itself
    :param ABR_Feedback_Controller: Provider Specific
    :param TC_Feedback_Controller: Do we use the File Policy or something else
    :param Provider: Which Provider are we sampling
    :param Model: Name of the model AdverserialTree,FilePolicy,RandomSampling
    :param video_urls: All video urls we want to sample
    :param existing_folder_policy: If we find the same folder do we ignore the setting or do we delete and recreate the folder
    :param use_virtual_display: do we use a virtual display, might be disabled for debugging purposes
    :return:
    """
    assert existing_folder_policy in ['replace', 'ignore', 'modify']
    logger.info('Logging Data for %s' % Model)
    large_display = None
    if use_virtual_display:
        large_display = Display(visible=False, size=(VIRTUAL_DISPLAY_WIDTH, VIRTUAL_DISPLAY_HEIGHT))
        large_display.start()
    if use_proxy:
        Network_Controller = NetworkControllerChrome()
        if proxy_version == 'browsermob':
            Network_Controller.stop_browsermob_server()
            Network_Controller.start_browsermob_server(browsermob_server_path=BROWSERMOB_PROXY_PATH)
            browser_proxy = Network_Controller.create_proxy(params=None)
        else:
            Network_Controller.stop_mitm_server()
            browser_proxy = Network_Controller.start_mitm_proxy(mitmproxy_server_path=MITMPROXY_PATH)
    else:
        browser_proxy = None
    try:
        # --------------------- Network Controller ( Iterate over the random policies for the time being)
        for iterator, video_url in enumerate(video_urls):
            logger.info('Sampling %s @Provider %s' % (video_url, Provider))
            result_path_formatted = RESULT_PATH_TEMPLATE.format(Provider=Provider, ScreenResolution='%sx%s' % (VIRTUAL_DISPLAY_WIDTH, VIRTUAL_DISPLAY_HEIGHT),
                                                                Model=Model,
                                                                ModelInstance=TC_Feedback_Controller.name)
            video_id = ABR_Feedback_Controller.extract_video_id(video_url)
            TC_Feedback_Controller.set_video_information(VIDEO_INFORMATION_PATH_TEMPLATE.format(Provider=Provider,
                                                                                                video_id=video_id))

            result_path_formatted += '/{VideoTraceID}'.format(VideoTraceID='video_%s_%s' % (video_id,
                                                                                            TC_Feedback_Controller.get_trace_id()))
            path_exists = False
            if os.path.exists(result_path_formatted):
                print('%s already exists : Number %d' % (result_path_formatted, iterator))
                if (existing_folder_policy == 'replace') or experiment_not_finished(result_path_formatted):
                    print('%s deleting' % result_path_formatted)
                    shutil.rmtree(result_path_formatted)
                    os.makedirs(result_path_formatted)
                elif existing_folder_policy == 'modify':
                    print('%s modifying ' % result_path_formatted)
                    experiment_iteration = 0
                    while os.path.exists(result_path_formatted + '_{experiment_iteration}'.format(
                            experiment_iteration=experiment_iteration)) and not experiment_not_finished(
                        result_path_formatted + '_{experiment_iteration}'.format(
                            experiment_iteration=experiment_iteration)):
                        experiment_iteration += 1
                    if experiment_iteration >= max_modify:
                        path_exists = True
                    else:
                        result_path_formatted = result_path_formatted + '_{experiment_iteration}'.format(
                            experiment_iteration=experiment_iteration)
                        if os.path.exists(result_path_formatted):
                            shutil.rmtree(result_path_formatted)
                        os.makedirs(result_path_formatted)
                else:
                    path_exists = True
            else:
                os.makedirs(result_path_formatted)
            if not path_exists:
                try:
                    Sampler = FeedbackSampler(browser_proxy=browser_proxy,
                                              TC_Feedback_Controller=TC_Feedback_Controller,
                                              ABR_Feedback_Controller=ABR_Feedback_Controller,
                                              logging_level=logging.DEBUG,
                                              result_path=result_path_formatted,
                                              video_url=video_url,
                                              DEBUG_MODE=False,
                                              browser_driver=CHROMEDRIVER_PATH,
                                              add_adblocker=add_adblocker,
                                              add_measurement_at_client=add_measurement_at_client)
                    Sampler.start()

                except ParsingError as parsing_Failed:
                    print('Failed Experiment %s with a ParsingError' % TC_Feedback_Controller.name)
                    print("ParsingError error: {0}s".format(parsing_Failed))
                    print('We will redo that experiment in the end')
                except TimeoutException as loading_failed:
                    print('Failed Experiment %s with a TimeoutException' % TC_Feedback_Controller.name)
                    print("TimeoutException error: {0}s".format(loading_failed))
                    print('We will redo that experiment in the end')
                except TimeoutError as loading_failed:
                    print('Failed Experiment %s with a TimeoutError' % TC_Feedback_Controller.name)
                    print("TimeoutError error: {0}s".format(loading_failed))
                    print('We will redo that experiment in the end')
                except NoSuchElementException as loading_failed:
                    print('Failed Experiment %s with a NoSuchElementException' % TC_Feedback_Controller.name)
                    print("NoSuchElementException error: {0}s".format(loading_failed))
                except ElementNotVisibleException as website_broke:
                    print('Failed Experiment %s with a ElementNotVisibleException' % TC_Feedback_Controller.name)
                    print("ElementNotVisibleException error: {0}s".format(website_broke))
                except ConnectionError as connection_lost:
                    print('Failed Experiment %s with a ConnectionError' % TC_Feedback_Controller.name)
                    print("ElementNotVisibleException error: {0}s".format(connection_lost))
                finally:
                    TC_Feedback_Controller.next_experiment()
            else:
                TC_Feedback_Controller.next_experiment()
    finally:
        print('Shutting down the Server and the Virtual display')
        if use_proxy:
            if proxy_version == 'browsermob':
                Network_Controller.stop_browsermob_server()
            else:
                Network_Controller.stop_mitm_server()

        if use_virtual_display:
            large_display.stop()
            try:  # -> cleanup leftovers
                os.remove('bmp.log')
                os.remove('server.log')
                os.remove('tc_*')
            except:
                print('Manually delete leftovers')
