import logging
import os
from abc import abstractmethod
from os.path import exists
from time import time

import numpy as np

from OfflineSimulator.OfflineSimulator import Environment, load_trace


class RewardFunction:

    @abstractmethod
    def return_reward(self, enviroment_state):
        pass


class BitrateQoE(RewardFunction):

    def __init__(self, rebuffer_penalty=4.3, smoothing_penality=1., reference_len_chunk_s=4.):
        self.reference_len_chunk_s = reference_len_chunk_s
        self.smoothing_penality = smoothing_penality
        self.rebuffer_penalty = rebuffer_penalty

    def return_reward(self, enviroment_state):
        reward = enviroment_state['current_bitrate'] * 1e-6 * (
                    enviroment_state['chunk_len_s'] / self.reference_len_chunk_s) \
                 - self.rebuffer_penalty * enviroment_state['rebuffering'] \
                 - self.smoothing_penality * np.abs(enviroment_state['current_bitrate'] -
                                                    enviroment_state['last_bitrate']) * 1e-6
        return reward


class VMAFQoE(BitrateQoE):
    """
    Taken from End - to - End transport for video qoe fairness
    """

    def __init__(self, rebuffer_penalty=25, smoothing_penality=2.5, reference_len_chunk_s=4.):
        super().__init__(rebuffer_penalty, smoothing_penality)
        self.reference_len_chunk_s = reference_len_chunk_s

    def return_reward(self, enviroment_state):
        reward = enviroment_state['current_vmaf'] * (enviroment_state['chunk_len_s'] /
                                                     self.reference_len_chunk_s) \
                 - self.rebuffer_penalty * enviroment_state['rebuffering'] \
                 - self.smoothing_penality * np.abs(enviroment_state['current_vmaf'] -
                                                    enviroment_state['last_vmaf'])
        return reward


M_IN_K = 1000.0

LOGGING_LEVEL = logging.INFO

handler = logging.StreamHandler()
handler.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
logger.addHandler(handler)


class MPC:
    """
    Adapted from https://github.com/hongzimao/pensieve
    """

    def __init__(self,
                 name,
                 reward_function: RewardFunction,
                 last_n_probes,
                 lookahead=5,
                 robust=True):
        self.robust = robust
        self.last_n_probes = last_n_probes
        self.reward_function = reward_function
        self.lookahead = lookahead
        self.name = name
        self.log_path = 'Data/Results/%s/' % self.name
        if not exists(self.log_path):
            os.makedirs(self.log_path)

    def solve_lookahead(self, net_env, lookahead_to_go, last_level, future_bandwidth, index, current_buffer):
        current_counter = net_env.video_chunk_counter + index
        if lookahead_to_go == 0 or current_counter >= len(net_env.byte_size_match):
            return 0, 0

        reward_list = []
        for next_level in range(net_env.max_quality_level + 1):
            size_mbit = 8e-6 * net_env.byte_size_match.iloc[current_counter, next_level]
            delay = size_mbit / future_bandwidth
            next_buffer = current_buffer - delay
            rebuf = 0
            if next_buffer < 0:
                rebuf = np.abs(next_buffer)
                next_buffer = 0
            next_buffer += net_env.video_information_csv.seg_len_s[current_counter] * 1000.
            current_iterator = max([net_env.video_chunk_counter - 1, 0])
            last_iterator = max([net_env.video_chunk_counter - 2, 0])

            enviroment_state = {'last_vmaf': net_env.get_vmaf(last_iterator, last_level),
                                'current_vmaf': net_env.get_vmaf(current_iterator, next_level),
                                'last_bitrate': net_env.get_bitrate(last_iterator, last_level),
                                'current_bitrate': net_env.get_bitrate(current_iterator, next_level),
                                'rebuffering': rebuf,
                                'chunk_len_s': net_env.video_information_csv.iloc[current_iterator].seg_len_s
                                }
            reward = self.reward_function.return_reward(enviroment_state)

            reward_return, _ = self.solve_lookahead(net_env, lookahead_to_go=lookahead_to_go - 1, last_level=next_level,
                                                    future_bandwidth=future_bandwidth,
                                                    index=index + 1,
                                                    current_buffer=next_buffer)

            reward_list.append(reward + reward_return)
        return np.max(reward_list), np.argmax(reward_list)

    def evaluate_video(self, trace_path,
                       video_file, video_id, filter_traces=None):
        current_log_path = self.log_path + video_file.split('/')[-2] + '/'
        if not os.path.exists(current_log_path):
            os.makedirs(current_log_path)

        all_cooked_time, all_cooked_bw, all_file_names = load_trace(trace_path, filter_traces)

        net_env = Environment(all_cooked_time=all_cooked_time,
                              all_cooked_bw=all_cooked_bw, video_information_csv=video_file)

        log_path = current_log_path + 'video_{video_id}_file_id_{file_name}'.format(
            video_id=video_id, file_name=all_file_names[net_env.trace_idx])
        while os.path.isfile(log_path) and len(open(log_path, 'r').read().split('\n')) >= len(
                net_env.video_information_csv):
            net_env.trace_idx += 1
            if net_env.trace_idx >= len(all_file_names):
                return
            log_path = current_log_path + 'video_{video_id}_file_id_{file_name}'.format(
                video_id=video_id, file_name=all_file_names[net_env.trace_idx])
        if os.path.isfile(log_path):
            os.remove(log_path)
        log_file = open(log_path, 'w')
        time_stamp = 0
        last_level = 0
        current_level = 0
        video_count = 0
        past_errors = []
        past_bandwidth_ests = []
        throughput_memory = []

        start_time = time()
        while True:  # serve video forever

            # the action is from the last decision
            # this is to make the framework similar to the real
            delay, sleep_time, buffer_size, rebuf, \
            video_chunk_size, next_video_chunk_sizes, \
            end_of_video, video_chunk_remain = \
                net_env.get_video_chunk(current_level)

            time_stamp += delay  # in ms
            time_stamp += sleep_time  # in ms

            # reward is video quality - rebuffer penalty
            current_iterator = max([net_env.video_chunk_counter - 1, 0])
            last_iterator = max([net_env.video_chunk_counter - 2, 0])

            enviroment_state = {'last_vmaf': net_env.get_vmaf(last_iterator, last_level),
                                'current_vmaf': net_env.get_vmaf(current_iterator, current_level),
                                'last_bitrate': net_env.get_bitrate(last_iterator, last_level),
                                'current_bitrate': net_env.get_bitrate(current_iterator, current_level),
                                'rebuffering': rebuf,
                                'chunk_len_s': net_env.video_information_csv.iloc[current_iterator].seg_len_s
                                }
            reward = self.reward_function.return_reward(enviroment_state)

            last_level = current_level

            # log time_stamp, current_level, buffer_size, reward
            log_file.write(str(time_stamp / M_IN_K) + '\t' +
                           str(net_env.get_bitrate(current_iterator, current_level)) + '\t' +
                           str(net_env.get_vmaf(current_iterator, current_level)) + '\t' +
                           str(buffer_size) + '\t' +
                           str(rebuf) + '\t' +
                           str(video_chunk_size) + '\t' +
                           str(net_env.video_information_csv.iloc[current_iterator].seg_len_s) + '\t' +
                           str(delay) + '\t' +
                           str(current_level) + '\t' +
                           str(reward) + '\n')

            # --------------------------------------------------------------------------------
            # Keep a history of the data

            throughput_memory.append((8e-6 * video_chunk_size) / (delay / M_IN_K))

            curr_error = 0  # defualt assumes that this is the first request so error is 0 since we have never predicted bandwidth
            if (len(past_bandwidth_ests) > 0):
                bw_estimate = throughput_memory[-1]
                curr_error = abs(past_bandwidth_ests[-1] - bw_estimate) / float(bw_estimate)
            past_errors.append(curr_error)

            past_bandwidths = throughput_memory[-5:]
            while past_bandwidths[0] == 0.0:
                past_bandwidths = past_bandwidths[1:]  # Mbit/s

            bandwidth_sum = 0
            for past_val in past_bandwidths:
                bandwidth_sum += (1 / float(past_val))
            harmonic_bandwidth = 1.0 / (bandwidth_sum / len(past_bandwidths))

            error_pos = -5
            if (len(past_errors) < 5):
                error_pos = -len(past_errors)
            max_error = float(max(past_errors[error_pos:]))
            if self.robust:
                future_bandwidth = harmonic_bandwidth / (1 + max_error)  # robustMPC here
            else:
                future_bandwidth = harmonic_bandwidth
            past_bandwidth_ests.append(harmonic_bandwidth)

            if len(throughput_memory) <= self.last_n_probes:
                # --------------- Startup behaviour
                current_video_bitrates_mbit = [net_env.get_bitrate(net_env.video_chunk_counter, i) * 1e-6 for i in
                                               range(net_env.max_quality_level + 1)]
                current_level = [rate <= throughput_memory[-1] for rate in current_video_bitrates_mbit]
                current_level = sum(current_level) - 1
                current_level = max([current_level, 0])
            else:
                _, current_level = self.solve_lookahead(net_env, self.lookahead, last_level=current_level,
                                                        future_bandwidth=future_bandwidth, index=0,
                                                        current_buffer=buffer_size)
            current_level = int(current_level)
            if end_of_video:
                logger.info('Finished watching video,took %.2f' % (time() - start_time))
                start_time = time()
                throughput_memory = []

                log_file.write('\n')
                log_file.close()

                last_level = 0
                current_level = 0  # use the default action here

                video_count += 1

                if video_count > len(all_file_names):
                    break

                log_path = current_log_path + 'video_{video_id}_file_id_{file_name}'.format(
                    video_id=video_id, file_name=all_file_names[net_env.trace_idx])
                while os.path.isfile(log_path) and len(open(log_path, 'r').read().split('\n')) >= len(
                        net_env.video_information_csv) - 5:
                    net_env.trace_idx += 1
                    if net_env.trace_idx >= len(all_file_names):
                        return
                    log_path = current_log_path + 'video_{video_id}_file_id_{file_name}'.format(
                        video_id=video_id, file_name=all_file_names[net_env.trace_idx])
                if os.path.isfile(log_path):
                    os.remove(log_path)
                log_file = open(log_path, 'w')
