import os

import numpy as np
import pandas as pd

from FeedbackSampler.Implementations.ChunkBasedFeedbackController import VimeoFeedbackController
from MainMethods import start_sampling
from OfflineSimulator.MPC import MPC, BitrateQoE
from TrafficController.TCFeedbackControllerChunk import TCFeedbackControllerFile

#########################################################
#### Testing Online Provider
ABR_Feedback_Controller = VimeoFeedbackController()
Provider = 'Vimeo'
use_virtual_display = False
video_csv = pd.read_csv('Data/SelectedVideoDataframe.csv')
vimeo_urls = video_csv[video_csv.Provider == 'Vimeo']
all_video_urls = vimeo_urls['Video Url'].values
network_interface_experiment = 'eno1' # Your Network Interface
trace_paths = []
for (dirpath, dirnames, filenames) in os.walk('Data/Traces/'):
    trace_paths.extend([os.path.join(dirpath, f) for f in filenames])
trace_paths = sorted(trace_paths)
local_password = ''  # Password needed to enabling tc with sudo
base_latency = 0
File_Client = TCFeedbackControllerFile(file_paths=trace_paths,
                                       separator=' ',
                                       network_interface=network_interface_experiment,
                                       pw=local_password,
                                       model_instance_type='ValidationFile',
                                       max_bandwidth_mbit=250,
                                       min_bandwidth_mbit=0.1,
                                       base_latency_ms=base_latency,
                                       throttle_type='tcset_raw',
                                       mode='iterative')
Model = 'File_Sampler'

validation_video_urls = np.random.choice(all_video_urls, size=len(trace_paths))
start_sampling(ABR_Feedback_Controller=ABR_Feedback_Controller,
               TC_Feedback_Controller=File_Client,
               Provider=Provider,
               Model=Model,
               video_urls=validation_video_urls,
               existing_folder_policy='ignore',
               use_proxy=True,
               use_virtual_display=use_virtual_display,
               add_adblocker=False,
               add_measurement_at_client=False)

########################################################
#### Testing Offline provider
mpc_simulator = MPC(name='mpc_example',
                    reward_function=BitrateQoE(),
                    last_n_probes=5,
                    lookahead=5,
                    robust=True)
for video_idx, video in enumerate(validation_video_urls):
    for info_folder in os.listdir('Data/VideoInformation'):
        for video_information_csv in os.listdir('Data/VideoInformation/' + info_folder):
            video_id = video_information_csv.replace('_video_info', '').strip()
            is_contained = [video_id in url for url in [video]]
            if sum(is_contained) == 1:
                video_file_csv = 'Data/VideoInformation/' + info_folder + '/' + video_information_csv
                mpc_simulator.evaluate_video(trace_path=trace_paths[video_idx], video_file=video_file_csv,
                                             video_id=video_id)
