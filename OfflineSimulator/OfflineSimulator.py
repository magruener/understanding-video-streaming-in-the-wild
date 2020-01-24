"""
Taken from
https://github.com/hongzimao/pensieve

"""

import os

import numpy as np
import pandas as pd

MILLISECONDS_IN_SECOND = 1000.0
B_IN_MB = 1000000.0
BITS_IN_BYTE = 8.0

def load_trace(cooked_trace_folder, keep_traces=None):
    cooked_files = os.listdir(cooked_trace_folder)
    all_cooked_time = []
    all_cooked_bw = []
    all_file_names = []
    for cooked_file in cooked_files:
        if keep_traces is not None and cooked_file not in keep_traces:
            continue
        file_path = cooked_trace_folder + cooked_file
        cooked_time = []
        cooked_bw = []
        # print file_path
        with open(file_path, 'rb') as f:
            for line in f:
                parse = line.split()
                cooked_time.append(float(parse[0]))
                cooked_bw.append(float(parse[1]))
        all_cooked_time.append(cooked_time)
        all_cooked_bw.append(cooked_bw)
        all_file_names.append(cooked_file)

    return all_cooked_time, all_cooked_bw, all_file_names

class Environment:
    def __init__(self,
                 all_cooked_time,
                 all_cooked_bw,
                 video_information_csv,
                 BUFFER_THRESH=60.0 * MILLISECONDS_IN_SECOND,
                 DRAIN_BUFFER_SLEEP_TIME=500.0,
                 PACKET_PAYLOAD_PORTION=0.95,
                 LINK_RTT=200,  # millisec,
                 PACKET_SIZE=1500):
        assert len(all_cooked_time) == len(all_cooked_bw)
        self.BUFFER_THRESH = BUFFER_THRESH
        self.DRAIN_BUFFER_SLEEP_TIME = DRAIN_BUFFER_SLEEP_TIME
        self.PACKET_PAYLOAD_PORTION = PACKET_PAYLOAD_PORTION
        self.LINK_RTT = LINK_RTT
        self.PACKET_SIZE = PACKET_SIZE
        self.all_cooked_time = all_cooked_time
        self.all_cooked_bw = all_cooked_bw

        self.video_chunk_counter = 0
        self.buffer_size = 0

        # pick a random trace file
        self.trace_idx = 0
        self.cooked_time = self.all_cooked_time[self.trace_idx]
        self.cooked_bw = self.all_cooked_bw[self.trace_idx]

        self.mahimahi_start_ptr = 1
        # randomize the start point of the trace
        # note: trace file starts with time 0
        self.mahimahi_ptr = self.mahimahi_start_ptr
        self.last_mahimahi_time = self.cooked_time[self.mahimahi_ptr - 1]

        def extract_sorted(key_str, column):
            column = list(filter(lambda c: key_str in c, column))
            column = sorted(column,
                            key=lambda c: np.array(c.split('_')[0].split('x')).astype(float).prod()
                            )
            return column

        self.video_information_csv = pd.read_csv(video_information_csv, index_col=0)
        self.video_information_csv['time_s'] = self.video_information_csv.seg_len_s.cumsum()
        self.byte_size_match = extract_sorted('byte', self.video_information_csv.columns)
        self.byte_size_match = self.video_information_csv[self.byte_size_match]
        self.vmaf_match = extract_sorted('vmaf', self.video_information_csv.columns)
        self.vmaf_match = self.video_information_csv[self.vmaf_match]
        self.bitrate_match = extract_sorted('bitrate', self.video_information_csv.columns)
        self.bitrate_match = self.video_information_csv[self.bitrate_match]
        self.max_quality_level = self.byte_size_match.shape[1] - 1
        self.video_duration = self.video_information_csv.seg_len_s.sum()
        self.TOTAL_VIDEO_CHUNCK = len(self.bitrate_match) - 1


    def get_vmaf(self,index,quality):
        assert len(self.vmaf_match) > index,'Index is to big %d %d' % (len(self.vmaf_match),index)
        return self.vmaf_match.iloc[index,quality]

    def get_bitrate(self,index,quality):
        assert len(self.bitrate_match) > index,'Index is to big'
        return self.bitrate_match.iloc[index,quality]

    def set_state(self, state):
        self.trace_idx = state['trace_idx']
        self.cooked_time = self.all_cooked_time[self.trace_idx]
        self.cooked_bw = self.all_cooked_bw[self.trace_idx]
        self.video_chunk_counter = state['video_chunk_counter']
        self.mahimahi_ptr = state['mahimahi_ptr']
        self.buffer_size = state['buffer_size']
        self.last_mahimahi_time = state['last_mahimahi_time']

    def save_state(self):
        return {'trace_idx': self.trace_idx,
                'mahimahi_ptr': self.mahimahi_ptr,
                'buffer_size': self.buffer_size,
                'video_chunk_counter': self.video_chunk_counter,
                'last_mahimahi_time': self.last_mahimahi_time}

    def get_video_chunk(self, quality):

        assert quality >= 0

        video_chunk_size = self.byte_size_match.iloc[self.video_chunk_counter, quality]

        # use the delivery opportunity in mahimahi
        delay = 0.0  # in ms
        video_chunk_counter_sent = 0  # in bytes

        while True:  # download video chunk over mahimahi
            throughput = self.cooked_bw[self.mahimahi_ptr] \
                         * B_IN_MB / BITS_IN_BYTE
            duration = self.cooked_time[self.mahimahi_ptr] \
                       - self.last_mahimahi_time

            packet_payload = throughput * duration * self.PACKET_PAYLOAD_PORTION

            if video_chunk_counter_sent + packet_payload > video_chunk_size:
                fractional_time = (video_chunk_size - video_chunk_counter_sent) / \
                                  throughput / self.PACKET_PAYLOAD_PORTION
                delay += fractional_time
                self.last_mahimahi_time += fractional_time
                break

            video_chunk_counter_sent += packet_payload
            delay += duration
            self.last_mahimahi_time = self.cooked_time[self.mahimahi_ptr]
            self.mahimahi_ptr += 1

            if self.mahimahi_ptr >= len(self.cooked_bw):
                # loop back in the beginning
                # note: trace file starts with time 0
                self.mahimahi_ptr = 1
                self.last_mahimahi_time = 0

        delay *= MILLISECONDS_IN_SECOND
        delay += self.LINK_RTT

        # rebuffer time
        rebuf = np.maximum(delay - self.buffer_size, 0.0)

        # update the buffer
        self.buffer_size = np.maximum(self.buffer_size - delay, 0.0)

        # add in the new chunk
        self.buffer_size += self.video_information_csv.iloc[self.video_chunk_counter].seg_len_s * 1000. # buffer size is in ms
        # sleep if buffer gets too large
        sleep_time = 0
        if self.buffer_size > self.BUFFER_THRESH:
            # exceed the buffer limit
            # we need to skip some network bandwidth here
            # but do not add up the delay_percent
            drain_buffer_time = self.buffer_size - self.BUFFER_THRESH
            sleep_time = np.ceil(drain_buffer_time / self.DRAIN_BUFFER_SLEEP_TIME) * \
                         self.DRAIN_BUFFER_SLEEP_TIME
            self.buffer_size -= sleep_time

            while True:
                duration = self.cooked_time[self.mahimahi_ptr] \
                           - self.last_mahimahi_time
                if duration > sleep_time / MILLISECONDS_IN_SECOND:
                    self.last_mahimahi_time += sleep_time / MILLISECONDS_IN_SECOND
                    break
                sleep_time -= duration * MILLISECONDS_IN_SECOND
                self.last_mahimahi_time = self.cooked_time[self.mahimahi_ptr]
                self.mahimahi_ptr += 1

                if self.mahimahi_ptr >= len(self.cooked_bw):
                    # loop back in the beginning
                    # note: trace file starts with time 0
                    self.mahimahi_ptr = 1
                    self.last_mahimahi_time = 0

        # the "last buffer size" return to the controller
        # Note: in old version of dash the lowest buffer is 0.
        # In the new version the buffer always have at least
        # one chunk of video
        return_buffer_size = self.buffer_size

        self.video_chunk_counter += 1
        video_chunk_remain = self.TOTAL_VIDEO_CHUNCK - self.video_chunk_counter

        end_of_video = False
        if self.video_chunk_counter >= self.TOTAL_VIDEO_CHUNCK:
            end_of_video = True
            self.buffer_size = 0
            self.video_chunk_counter = 0

            self.trace_idx += 1
            if self.trace_idx >= len(self.all_cooked_time):
                self.trace_idx = 0

            self.cooked_time = self.all_cooked_time[self.trace_idx]
            self.cooked_bw = self.all_cooked_bw[self.trace_idx]

            # randomize the start point of the video
            # note: trace file starts with time 0

            self.mahimahi_ptr = self.mahimahi_start_ptr
            self.last_mahimahi_time = self.cooked_time[self.mahimahi_ptr - 1]

        next_video_chunk_sizes = []
        for i in range(self.max_quality_level + 1):
            next_video_chunk_sizes.append(self.byte_size_match.iloc[self.video_chunk_counter, i])

        return delay, \
               sleep_time, \
               return_buffer_size / MILLISECONDS_IN_SECOND, \
               rebuf / MILLISECONDS_IN_SECOND, \
               video_chunk_size, \
               next_video_chunk_sizes, \
               end_of_video, \
               video_chunk_remain
