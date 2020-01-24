import logging
import os
import threading
import time
from abc import ABC, abstractmethod

import blist
import numpy as np
import pandas as pd

LOGGING_LEVEL = logging.INFO

handler = logging.StreamHandler()
handler.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
logger.addHandler(handler)

throttle_types = ['browsermobproxy', 'selenium', 'tcset', 'tcset_raw']


def get_current_unix():
    return time.time()


class ParsingError(Exception):
    """Raised when the input value is too small"""
    pass


class TCFeedbackControllerChunk(ABC):
    """
    Used to control the interaction between the python script and the tc shell scripts
    """

    def __init__(self,
                 network_interface='wlp4s0',
                 pw=None,
                 logging=True,
                 model_instance_type='default',
                 base_latency_ms='200',
                 base_throttle_mbit='3.',
                 min_bandwidth_mbit=0.75,
                 max_bandwidth_mbit=8.,
                 max_shift=2,
                 buffer_inaccuarcy_s=1.5,
                 throttle_type='selenium'):

        assert throttle_type in throttle_types, "Choose throttle type from %s" % throttle_types
        self.throttle_type = throttle_type
        self.video_quality_mapper = None
        self.max_shift = max_shift
        self.min_bandwidth_mbit = min_bandwidth_mbit
        self.max_bandwidth_mbit = max_bandwidth_mbit
        self.base_throttle_mbit = base_throttle_mbit
        self.current_throttle_mbit = float(base_throttle_mbit)
        self.base_latency_ms = base_latency_ms
        self.byte_size_match = None
        if pw is None:
            pw = ''
        logger.info('Set password to %s,len() = %d' % (pw, len(pw)))
        self.pw = pw
        self.dev_interface = network_interface
        self.name = model_instance_type
        self.tc_process = None
        self.run_calculation = False
        self.tc_path = '/sbin/tc'
        self.logging_file = None
        self.logging = logging
        self.video_information_csv = None
        self.media_request_dataframe = None
        self.max_quality_level = None
        self.max_segment_number = None
        self.parent_path = None
        self.video_duration = None
        self.buffer_list = []
        self.tentative_streambuckets = blist.sortedlist([[0.0, 0.0, 0.0]], key=lambda k: k[0])
        self.sorted_by_timestamp_finished = blist.sortedlist([],
                                                             key=lambda parsed_entry: parsed_entry['timestamp_finish'])
        self.sorted_by_timestamp_start = blist.sortedlist([], key=lambda parsed_entry: parsed_entry['timestamp_start'])
        self.sorted_by_segment_start_time = blist.sortedlist([], key=lambda parsed_entry: parsed_entry['t_start'])
        self.shifts = np.arange(-self.max_shift, self.max_shift + 1)
        self.latest_buffer_value_timestamp = None
        self.newly_recorded_index = 0
        self.last_buffer_index = -1
        self.latest_buffer_value = 0
        self.latest_accumulated_rebuffer_value = 0.
        self.path_video_id = None
        self.start_time = time.time()
        self.buffer_inaccuarcy_s = buffer_inaccuarcy_s
        self.browser = None
        self.proxy = None
        self.pw_min_len = 2
        self.max_mult_video = 4.0

    def start_new_streaming(self):
        self.buffer_list = []
        self.tentative_streambuckets = blist.sortedlist([[0.0, 0.0, 0.0]], key=lambda k: k[0])
        self.sorted_by_timestamp_finished = blist.sortedlist([],
                                                             key=lambda parsed_entry: parsed_entry['timestamp_finish'])
        self.sorted_by_timestamp_start = blist.sortedlist([], key=lambda parsed_entry: parsed_entry['timestamp_start'])
        self.sorted_by_segment_start_time = blist.sortedlist([], key=lambda parsed_entry: parsed_entry['t_start'])
        self.shifts = np.arange(-self.max_shift, self.max_shift + 1)
        self.latest_buffer_value_timestamp = None
        self.newly_recorded_index = 0
        self.last_buffer_index = -1
        self.latest_buffer_value = 0
        self.latest_accumulated_rebuffer_value = 0.
        self.start_time = time.time()

    def set_parent_logging_path(self, parent_path):
        self.parent_path = parent_path

    def set_video_information(self, path_video_id):
        logger.info('Setting new Video %s' % path_video_id)
        self.path_video_id = path_video_id
        self.load_video_information(path_video_id)
        self.load_quality_mapper(path_video_id)

    def clean_url(self, media_request_url):
        quality_level_chosen = self.video_quality_mapper.contained_in_url.map(lambda cnt_url: sum(
            [True if c in media_request_url else False for c in cnt_url]) > 0)
        index = np.where(quality_level_chosen)
        if len(index[0]) == 1:
            replace_str = self.video_quality_mapper.remove_segment_identifier.iloc[index[0][0]]
            if replace_str != 'dummy_value':
                media_request_url = media_request_url.replace(replace_str, '')
        return media_request_url

    def finished_checker(self):
        if self.video_information_csv is None:
            raise ValueError("We're missing video information - "
                             "can't determine whether we have already downloaded everything")
        if self.video_duration is None:
            raise ValueError("We're missing video information - "
                             "can't determine whether we have already downloaded everything")
        if (time.time() - self.start_time) * self.max_mult_video > self.video_duration:
            return True
        if len(self.buffer_list) == 0:  # We haven't buffered anything
            logger.debug("We haven't buffered anything %s" % self.buffer_list)
            start_time_filtered = [(r['t_start'], r['t_end']) for r in self.sorted_by_timestamp_finished]
            logger.debug("We haven't buffered anything %s" % start_time_filtered)
            return False
        # logger.debug(
        #   'Currently bufferd up until %.2f, video duration is %.2f' % (self.buffer_list[-1][1], self.video_duration))
        # logger.info("Currently bufferd %s" % self.buffer_list)
        start_time_filtered = [(r['t_start'], r['t_end']) for r in self.sorted_by_timestamp_finished]
        # logger.info("Currently bufferd %s" % self.tentative_streambuckets)
        # logger.info("We have played %.2f seconds of at maximum %.2f" % (time.time() - self.start_time,self.video_duration) )
        # logger.debug('We have been playing for %.2f seconds' % (time.time() - self.start_time))
        return self.video_duration <= self.buffer_list[-1][1]

    def load_video_information(self, path_video_id):
        path_to_csv = path_video_id + '_video_info'

        def extract_sorted(key_str, column):
            column = list(filter(lambda c: key_str in c, column))
            column = sorted(column,
                            key=lambda c: np.array(c.split('_')[0].split('x')).astype(float).prod()
                            )
            return column

        self.video_information_csv = pd.read_csv(path_to_csv)
        self.video_information_csv['time_s'] = self.video_information_csv.seg_len_s.cumsum()
        self.byte_size_match = extract_sorted('byte', self.video_information_csv.columns)
        self.byte_size_match = self.video_information_csv[self.byte_size_match]

        self.vmaf_match = extract_sorted('vmaf', self.video_information_csv.columns)
        self.vmaf_match = self.video_information_csv[self.vmaf_match]

        self.bitrate_match = extract_sorted('bitrate', self.video_information_csv.columns)
        self.bitrate_match = self.video_information_csv[self.bitrate_match]
        self.bitrate_encoded_mapper = {k: v for k, v in enumerate(self.bitrate_match.mean(0).values)}

        self.max_quality_level = self.byte_size_match.shape[1] - 1
        self.video_duration = self.video_information_csv.seg_len_s.sum()


    def load_quality_mapper(self, path_video_id):
        quality_mapper = path_video_id + '_video_quality_mapper'
        self.video_quality_mapper = pd.read_csv(quality_mapper, index_col=0)
        self.video_quality_mapper.contained_in_url = self.video_quality_mapper.contained_in_url.map(
            lambda cnt_url: [x.strip()[1:-1] for x in cnt_url[1:-1].split(',')] if
            cnt_url.startswith('[') else [cnt_url])

    def parse_newly_downloaded(self, newly_downloaded):
        parsed_entry_index = 0
        while parsed_entry_index < len(newly_downloaded):
            parsed_entry = newly_downloaded[parsed_entry_index]
            n_segment = int(parsed_entry['n_segment'])
            if 'segment_mapper' in self.video_information_csv:
                n_segment = np.searchsorted(self.video_information_csv.segment_mapper.astype(int), n_segment)
                parsed_entry['n_segment'] = n_segment
            if n_segment >= len(self.video_information_csv):
                logger.info(
                    'n_segment has been parsed incorrectly {n_segment} {url} \n maximum len {video_length} \n at {video_id}'.format(
                        n_segment=parsed_entry['n_segment'], url=parsed_entry['url'],
                        video_length=len(self.video_information_csv), video_id=self.path_video_id
                    ))
                newly_downloaded.remove(parsed_entry)
                logger.info('Removed entry still have %d new entries' % (len(newly_downloaded)))
                continue
            seg_len_s = self.video_information_csv.seg_len_s.iloc[n_segment]
            quality_level_chosen = self.video_quality_mapper.contained_in_url.map(lambda cnt_url: sum(
                [True if c in parsed_entry['url'] else False for c in cnt_url]) > 0)
            if quality_level_chosen.values.sum() != 1:
                logger.info('We have found an imparsable url {url}\npossible matches : {contained_in_url}'.format(
                    url=parsed_entry['url'], contained_in_url=self.video_quality_mapper.contained_in_url))
                newly_downloaded.remove(parsed_entry)
                logger.info('Removed entry still have %d new entries' % (len(newly_downloaded)))
                continue

            parsed_entry_index += 1
            parsed_entry['seg_len_s'] = seg_len_s
            parsed_entry['t_start'] = np.around(self.video_information_csv.time_s.iloc[n_segment] - seg_len_s, 2)
            parsed_entry['t_end'] = np.around(parsed_entry['t_start'] + seg_len_s, 2)
            quality_level_chosen = self.video_quality_mapper.quality_level[quality_level_chosen].values[0]
            parsed_entry['quality_level_chosen'] = quality_level_chosen
            parsed_entry['bitrate_level'] = self.bitrate_match.iloc[n_segment].values[quality_level_chosen]
            parsed_entry['vmaf_level'] = self.vmaf_match.iloc[n_segment].values[quality_level_chosen]

    def parse_newly_recorded(self, newly_recorded):
        logger.debug('Parsing newly recorded files %d' % len(newly_recorded))
        self.parse_newly_downloaded(newly_downloaded=newly_recorded)
        logger.debug('Parsed newly recorded files %d' % len(newly_recorded))

        for parsed_entry in newly_recorded:
            previous_quality = self.determine_previous_quality(parsed_entry)
            parsed_entry['previous_quality'] = previous_quality
            self.add_features(parsed_entry)
            parsed_entry['quality_shift'] = parsed_entry[
                                                'previous_quality'] - parsed_entry['quality_level_chosen']

    def update_media_requests(self, newly_downloaded, newly_recorded):
        self.parse_newly_downloaded(newly_downloaded)
        self.parse_newly_recorded(newly_recorded)
        self.update_buffer(newly_downloaded)
        self.sorted_by_timestamp_finished.update(newly_downloaded)
        self.sorted_by_timestamp_start.update(newly_recorded)
        self.sorted_by_segment_start_time.update(newly_recorded)
        self.update_sorted_by_started()

    def determine_previous_quality(self, parsed_entry):
        t_start = parsed_entry['t_start']
        parsed_entry['t_start'] = parsed_entry['t_end']
        idx = self.sorted_by_segment_start_time.bisect_right(parsed_entry)
        parsed_entry['t_start'] = t_start
        previous_quality = -1
        overlap_len = 0
        while idx < len(self.sorted_by_segment_start_time) and parsed_entry['t_start'] <= \
                self.sorted_by_segment_start_time[idx]['t_end']:
            overlap_left = max([parsed_entry['t_start'], self.sorted_by_segment_start_time[idx]['t_start']])
            overlap_right = min([parsed_entry['t_end'], self.sorted_by_segment_start_time[idx]['t_end']])
            # print('[%.2f,%.2f]' % (downloaded['t_start'], downloaded['t_end']), '[%.2f,%.2f]' % (
            #   sorted_by_t_start[idx]['t_start'], sorted_by_t_start[idx]['t_end']))
            if overlap_right - overlap_left > overlap_len and parsed_entry['timestamp_start'] > \
                    self.sorted_by_segment_start_time[idx][
                        'timestamp_start']:  # You have to have to have made this decision before you use it here
                parsed_entry['previous_bitrate'] = self.sorted_by_timestamp_start[idx]['bitrate_level']
                parsed_entry['previous_vmaf'] = self.sorted_by_timestamp_start[idx]['vmaf_level']
                previous_quality = self.sorted_by_segment_start_time[idx]['quality_level_chosen']
            # print(overlap_right - overlap_left, idx)
            idx -= 1
            if idx < 0:
                break
        # print('next', previous_quality)
        if previous_quality == -1:  # We haven't found an overlapping decision
            # Search for the quality that has been downloaded before this quality
            idx = self.sorted_by_timestamp_start.bisect(parsed_entry)  # Index  + 1 of that of this value
            idx -= 2
            if idx < 0:
                parsed_entry['previous_bitrate'] = 0  # We do
                parsed_entry['previous_vmaf'] = 0
                return 0
            else:
                assert self.sorted_by_timestamp_start[idx]['timestamp_start'] < parsed_entry['timestamp_start']
                parsed_entry['previous_bitrate'] = self.sorted_by_timestamp_start[idx]['bitrate_level']
                parsed_entry['previous_vmaf'] = self.sorted_by_timestamp_start[idx]['vmaf_level']
                return self.sorted_by_timestamp_start[idx]['quality_level_chosen']
        else:

            return previous_quality

    def add_features(self, parsed_entry, lookback=10, timestamp_shift=0):
        n_segment = int(parsed_entry['n_segment'])
        quality_level = int(parsed_entry['previous_quality'])
        possible_shifts = np.clip(np.arange(quality_level - self.max_shift,
                                            quality_level + self.max_shift + 1), a_min=0,
                                  a_max=self.max_quality_level)
        for shift_index, actual_shift in zip(self.shifts, possible_shifts):
            if n_segment < len(self.byte_size_match):
                parsed_entry['quality_shift_byte_%d' % shift_index] = self.byte_size_match.iloc[
                    n_segment].values[
                    actual_shift]
                parsed_entry['quality_shift_vmaf_%d' % shift_index] = self.vmaf_match.iloc[
                    n_segment].values[
                    actual_shift]
                parsed_entry['quality_shift_bitrate_%d' % shift_index] = self.bitrate_match.iloc[
                    n_segment].values[
                    actual_shift]
            else:
                parsed_entry['quality_shift_byte_%d' % shift_index] = np.nan
                parsed_entry['quality_shift_vmaf_%d' % shift_index] = np.nan
                parsed_entry['quality_shift_bitrate_%d' % shift_index] = np.nan
        timestamp_finish = parsed_entry['timestamp_finish']
        parsed_entry['timestamp_finish'] = parsed_entry['timestamp_start']
        idx_first_before = self.sorted_by_timestamp_finished.bisect_left(parsed_entry)  # find the entry in downloads
        if idx_first_before == len(self.sorted_by_timestamp_finished):  # The download at the end of all downloads
            idx_first_before -= 1
        parsed_entry['timestamp_finish'] = timestamp_finish
        logger.debug("Adding features to download started at %d, it's at index %d" % (
            parsed_entry['timestamp_start'], idx_first_before))
        logger.debug("We have downloaded %d segments" % len(self.sorted_by_timestamp_finished))
        logger.debug("We have started downloading %d segments" % len(self.sorted_by_timestamp_start))

        for i in range(min([lookback, idx_first_before])):
            if idx_first_before - i < 0:  # We might want to look back further than we can -> just ignore those indices
                continue
            parsed_entry['t_download_s_-{timestamp}'.format(timestamp=i + 1 + timestamp_shift)] = \
                self.sorted_by_timestamp_finished[
                    idx_first_before - i][
                    't_download_s']
            parsed_entry['quality_level_chosen_-{timestamp}'.format(timestamp=i + 1 + timestamp_shift)] = \
                self.sorted_by_timestamp_finished[
                    idx_first_before - i][
                    'quality_level_chosen']
            parsed_entry['bandwidth_mbit_-{timestamp}'.format(timestamp=i + 1 + timestamp_shift)] = \
                self.sorted_by_timestamp_finished[
                    idx_first_before - i][
                    'bandwidth_mbit']

    def update_sorted_by_started(self,
                                 timestamp_of_reference='timestamp_start',
                                 add_timestamp_of_reference=False):
        self.newly_recorded_index = 0
        self.last_buffer_index = 0
        self.latest_accumulated_rebuffer_value = 0
        self.latest_buffer_value = 0
        self.latest_buffer_value_timestamp = None
        while True:
            if self.newly_recorded_index >= len(self.sorted_by_timestamp_start) and self.last_buffer_index + 1 >= len(
                    self.buffer_list):
                break
            if self.newly_recorded_index < len(self.sorted_by_timestamp_start):
                parsed_entry = self.sorted_by_timestamp_start[self.newly_recorded_index]
                parsed_entry_timestamp = parsed_entry[timestamp_of_reference]
            else:
                parsed_entry = None
            # Decide which event comes first

            if self.last_buffer_index + 1 < len(self.buffer_list):
                last_buffer_timestamp = self.buffer_list[self.last_buffer_index + 1][2]
                buffer_added = self.buffer_list[self.last_buffer_index + 1][1] - self.buffer_list[
                    self.last_buffer_index + 1][0]
                if self.newly_recorded_index >= len(
                        self.sorted_by_timestamp_start) or last_buffer_timestamp < parsed_entry_timestamp:
                    # buffer event comes next
                    if self.latest_buffer_value_timestamp is None:
                        self.latest_buffer_value_timestamp = last_buffer_timestamp
                    time_diff = last_buffer_timestamp - self.latest_buffer_value_timestamp
                    self.latest_buffer_value -= time_diff
                    self.latest_buffer_value_timestamp = last_buffer_timestamp
                    if self.latest_buffer_value < 0:
                        self.latest_accumulated_rebuffer_value += -self.latest_buffer_value
                        self.latest_buffer_value = 0
                        # print('Rebuffered by %2.f' % accumulated_rebuffer)
                    self.latest_buffer_value += buffer_added
                    # print('Topped up buffer by %.2f -> %.2f at %.2f difference %.2f' % (buffer_added,last_buffer_value,last_timestamp,time_diff))
                    self.last_buffer_index += 1
                else:
                    if self.latest_buffer_value_timestamp is None:
                        self.latest_buffer_value_timestamp = parsed_entry_timestamp
                    if parsed_entry_timestamp < self.latest_buffer_value_timestamp :
                        error_str = 'The time we last evaluated the buffer is larger than the start time of this entry : buffer index %d / %d,started_entry index %d/%d' % (
                        self.last_buffer_index, len(self.buffer_list), self.newly_recorded_index,
                        len(self.sorted_by_timestamp_start))
                        raise ParsingError(error_str)

                    time_diff = parsed_entry_timestamp - self.latest_buffer_value_timestamp
                    self.latest_buffer_value -= time_diff
                    self.latest_buffer_value_timestamp = parsed_entry_timestamp
                    if self.latest_buffer_value < 0:
                        self.latest_accumulated_rebuffer_value += -self.latest_buffer_value
                        self.latest_buffer_value = 0
                    if add_timestamp_of_reference:
                        parsed_entry['buffer_level_at_%s' % timestamp_of_reference] = self.latest_buffer_value
                        parsed_entry[
                            'rebuffer_level_at_%s' % timestamp_of_reference] = self.latest_accumulated_rebuffer_value
                    else:
                        parsed_entry['buffer_estimate_0'] = self.latest_buffer_value
                        parsed_entry['rebuffer_estimate_0'] = self.latest_accumulated_rebuffer_value

                    self.latest_accumulated_rebuffer_value = 0
                    self.newly_recorded_index += 1
                    # print('Recorded Buffer state %.2f at %.2f difference %.2f' % (last_buffer_value,last_timestamp,time_diff))
            else:
                if self.latest_buffer_value_timestamp is None:
                    self.latest_buffer_value_timestamp = parsed_entry_timestamp
                if parsed_entry_timestamp < self.latest_buffer_value_timestamp:
                    error_str = 'The time we last evaluated the buffer is larger than the start time of this entry : buffer index %d / %d,started_entry index %d/%d' % (
                    self.last_buffer_index, len(self.buffer_list), self.newly_recorded_index,
                    len(self.sorted_by_timestamp_start))
                    raise ParsingError(error_str)
                time_diff = parsed_entry_timestamp - self.latest_buffer_value_timestamp
                self.latest_buffer_value -= time_diff
                self.latest_buffer_value_timestamp = parsed_entry_timestamp
                if self.latest_buffer_value < 0:
                    self.latest_accumulated_rebuffer_value += -self.latest_buffer_value
                    self.latest_buffer_value = 0
                if add_timestamp_of_reference:
                    parsed_entry['buffer_level_at_%s' % timestamp_of_reference] = self.latest_buffer_value
                    parsed_entry[
                        'rebuffer_level_at_%s' % timestamp_of_reference] = self.latest_accumulated_rebuffer_value
                else:
                    parsed_entry['buffer_estimate_0'] = self.latest_buffer_value
                    parsed_entry['rebuffer_estimate_0'] = self.latest_accumulated_rebuffer_value
                self.newly_recorded_index += 1
                self.latest_accumulated_rebuffer_value = 0

    def update_buffer(self, newly_downloaded):
        # buffer_list = []
        for parsed_entry in newly_downloaded:
            t_start = parsed_entry['t_start']
            t_end = parsed_entry['t_end']
            t_download_end = parsed_entry['timestamp_finish']
            t = [t_start, t_end, t_download_end]
            self.tentative_streambuckets.add(t)
            idx = self.tentative_streambuckets.index(t)
            current_max_stream = self.tentative_streambuckets[0][1]
            # print('Inserted %s' % t)
            # print('iteration %s' % tentative_streambuckets)
            if idx == 0:  # first item
                pass
                # print('Buffered %d -> %d at %d' % (t[0],t[1],t_download_end))
            else:
                if (idx + 1) < len(self.tentative_streambuckets):
                    if self.tentative_streambuckets[idx + 1][0] <= (t[1] + self.buffer_inaccuarcy_s):
                        self.tentative_streambuckets[idx][1] = max([t[1], self.tentative_streambuckets[idx + 1][
                            1]])
                        self.tentative_streambuckets[idx][0] = min([t[0], self.tentative_streambuckets[idx + 1][
                            0]])
                        del self.tentative_streambuckets[idx + 1]
                        # print('overlapped on the right')
                if self.tentative_streambuckets[idx - 1][1] >= (t[0] - self.buffer_inaccuarcy_s):
                    self.tentative_streambuckets[idx - 1][1] = max([t[1], self.tentative_streambuckets[idx - 1][
                        1]])
                    self.tentative_streambuckets[idx - 1][0] = min([t[0], self.tentative_streambuckets[idx - 1][
                        0]])
                    del self.tentative_streambuckets[idx]
                    # print('overlapped on the left')
                if self.tentative_streambuckets[0][1] > current_max_stream:
                    # print('Buffered %.2f -> %.2f at %d' % (current_max_stream,
                    #                                   tentative_streambuckets[0][1],
                    #                                   t_download_end))
                    self.buffer_list.append([current_max_stream, self.tentative_streambuckets[0][1], t_download_end])

    def __browsermobproxy_init(self):
        self.__browsermobproxy_throttle(float(self.base_throttle_mbit), float(self.base_latency_ms))

    def __browsermobproxy_throttle(self, bandwidth_mbit, latency_ms=None):
        if latency_ms is None:
            latency_ms = float(self.base_latency_ms)
        kbps_throttle = bandwidth_mbit * 125  # mbit to kbyte
        kbps_throttle = int(kbps_throttle)
        logger.debug('Throttling Browsermobproxy with %s kbyte throttle %s (mbit)' % (kbps_throttle, bandwidth_mbit))
        self.proxy.limits(options={'downstream_kbps': kbps_throttle,
                                   'upstream_kbps': kbps_throttle,
                                   'latency': latency_ms}
                          )

    def __selenium_init(self):
        self.__selenium_throttle(float(self.base_throttle_mbit), float(self.base_latency_ms))

    def __selenium_throttle(self, bandwidth_mbit, latency_ms=None):
        if latency_ms is None:
            latency_ms = float(self.base_latency_ms)
        byte_throttle = bandwidth_mbit * 125000
        byte_throttle = int(byte_throttle)
        logger.debug('Throttling Selenium with %s byte throttle %s (mbit)' % (byte_throttle, bandwidth_mbit))
        self.browser.set_network_conditions(
            offline=False,
            latency=latency_ms,  # additional latency (ms)
            download_throughput=byte_throttle,  # maximal throughput in kbit
            upload_throughput=byte_throttle)  # maximal throughput in kbit

    def __tc_init(self):
        """
                        Init the traffic control
                        https://serverfault.com/questions/350023/tc-ingress-policing-and-ifb-mirroring
                        :return:
                        """
        """
        init_throttle = ['sudo  modprobe ifb',
                         'sudo  ip link set dev ifb0 up',
                         'sudo %s qdisc add dev %s ingress' % (self.tc_path, self.dev_interface),
                         'sudo %s filter add dev %s parent ffff: protocol ip u32 match u32 0 0 flowid 1:1 action mirred egress redirect dev ifb0' % (
                             self.tc_path, self.dev_interface),
                             'sudo %s qdisc add dev ifb0 root tbf rate 1mbit latency 50ms burst 1540' % self.tc_path]
        """
        init_throttle = [
            'sudo modprobe ifb numifbs=1',
            # --------- Add relay
            'sudo tc qdisc add dev {dev_interface} handle ffff: ingress'.format(dev_interface=self.dev_interface),
            # -----------  enable the ifb interfaces:
            'sudo ifconfig ifb0 up',
            # -------- And redirect ingress traffic from the physical interfaces to corresponding ifb interface. For wlp4s0 -> ifb0:
            'sudo {tc_path} filter add dev {dev_interface} parent ffff: protocol all u32 match u32 0 0 action mirred egress redirect dev ifb0'.format(
                tc_path=self.tc_path,
                dev_interface=self.dev_interface),
            # -------------- Limit Speed
            'sudo {tc_path} qdisc add dev ifb0 root tbf rate {base_speed_mbit}mbit latency 50ms burst 1540'.format(
                tc_path=self.tc_path, base_speed_mbit=self.base_throttle_mbit)
        ]
        return init_throttle

    def __tc_throttle(self, bandwidth_mbit, latency_ms=None):
        if latency_ms is None:
            latency_ms = self.base_latency_ms
        throttle_cmd = 'sudo {tc_path} qdisc change dev ifb0 root tbf rate {bandwidth_mbit}mbit latency 50ms burst 1540'
        cmd = throttle_cmd.format(tc_path=self.tc_path, bandwidth_mbit=bandwidth_mbit)
        return [cmd]

    def __tc_clean(self):
        return ['sudo %s qdisc del dev %s ingress' % (self.tc_path, str(self.dev_interface)),
                'sudo %s qdisc del dev ifb0 root' % self.tc_path]

    def __tc_set_init(self):
        init_throttle = [
            'sudo tcset {dev_interface} --rate {base_speed_mbit}Mbps --delay {base_latency_ms}ms --direction incoming'.format(
                dev_interface=self.dev_interface, base_latency_ms=self.base_latency_ms,
                base_speed_mbit=self.base_throttle_mbit
            )]
        return init_throttle

    def __tc_set_throttle(self, bandwidth_mbit, latency_ms=None):
        if latency_ms is None:
            latency_ms = self.base_latency_ms
        return [
            'sudo tcset {dev_interface} --rate {bandwidth_mbit}Mbps --delay {latency_ms}ms --direction incoming --change'.format(
                dev_interface=self.dev_interface, latency_ms=latency_ms,
                bandwidth_mbit=bandwidth_mbit
            )]

    def __tc_set_clean(self):
        return ['sudo tcdel {dev_interface} --all'.format(dev_interface=self.dev_interface)]

    def prepare_throttle(self):
        if self.throttle_type == 'selenium':
            self.__selenium_init()
        elif self.throttle_type == 'browsermobproxy':
            self.__browsermobproxy_init()
        else:
            if self.throttle_type == 'tcset':
                cmds = self.__tc_set_init()
            else:
                cmds = self.__tc_init()
            for cmd in cmds:
                logger.info('Spawning %s ' % cmd)
                if len(self.pw) < self.pw_min_len:  # No password provided
                    os.system(cmd)
                else:
                    os.system('echo %s | sudo -S %s' % (self.pw, cmd))

    def init_throttle(self):
        self.start_new_streaming()

    def throttle(self, bandwidth_mbit):
        """
        :param bandwidth_mbit: bandwidth in mbit to which we want to restrict the download speed
        :param duration: duration of the limitation
        :return:
        """
        bandwidth_mbit = np.clip(bandwidth_mbit, a_min=self.min_bandwidth_mbit,
                                 a_max=self.max_bandwidth_mbit)  # clipping to reasonable values
        if self.logging_file is None and self.logging:
            self.logging_file = open(self.parent_path + '/throttle_logging.tc', 'w')
        self.current_throttle_mbit = bandwidth_mbit

        if self.throttle_type == 'selenium':
            self.__selenium_throttle(bandwidth_mbit=bandwidth_mbit)
        elif self.throttle_type == 'browsermobproxy':
            self.__browsermobproxy_throttle(bandwidth_mbit=bandwidth_mbit)
        else:
            if self.throttle_type == 'tcset':
                cmds = self.__tc_set_throttle(bandwidth_mbit=bandwidth_mbit)
            else:
                cmds = self.__tc_throttle(bandwidth_mbit=bandwidth_mbit)
            for cmd in cmds:
                logger.info('Spawning %s ' % cmd)
                if len(self.pw) < self.pw_min_len:  # No password provided
                    os.system(cmd)
                else:
                    os.system('echo %s | sudo -S %s' % (self.pw, cmd))

        logging_output = '%.3f\t%.3f\n' % (get_current_unix(), bandwidth_mbit)
        self.logging_file.write(logging_output)
        logger.debug('Writing %s' % logging_output)
        logger.info('Throtteling @%.2f Mbps with %s' % (bandwidth_mbit, self.throttle_type))

    def stop_throttle(self):

        if self.logging_file is not None:
            logging_output = '%.3f\t%.3f\n' % (get_current_unix(), self.current_throttle_mbit)
            self.logging_file.write(logging_output)
            self.logging_file.close()
            self.logging_file = None

        if self.throttle_type == 'selenium':
            logger.debug('Doing nothing as the browser is already closed')
        elif self.throttle_type == 'browsermobproxy':
            if self.proxy is not None:
                self.__browsermobproxy_throttle(100, 0)  # Resetting to standarts we anyhow can't attain
        else:
            if self.throttle_type == 'tcset':
                cmds = self.__tc_set_clean()
            else:
                cmds = self.__tc_clean()
            for cmd in cmds:
                logger.info('Spawning %s ' % cmd)
                if len(self.pw) < self.pw_min_len:  # No password provided
                    os.system(cmd)
                else:
                    os.system('echo %s | sudo -S %s' % (self.pw, cmd))

        self.proxy = None
        self.browser = None

    def save_experiment(self):
        if len(self.sorted_by_timestamp_start) > 0:
            pd.DataFrame(self.sorted_by_timestamp_start).to_csv(self.parent_path + '/inorder_dataframe.csv')
            pd.DataFrame(self.sorted_by_timestamp_finished).to_csv(self.parent_path + '/raw_dataframe.csv')

    @abstractmethod
    def get_trace_id(self):
        pass

    @abstractmethod
    def next_experiment(self):
        pass

    def enable_browser_access(self, browser):
        self.browser = browser

    def enable_proxy_access(self, proxy):
        self.proxy = proxy


class TCFeedbackControllerChunkConstant(TCFeedbackControllerChunk):

    def next_experiment(self):
        pass

    def get_trace_id(self):
        return 'bw_%.2f' % self.constant_bw_mbit

    def __init__(self, constant_bw_mbit, network_interface='wlp4s0', pw=None, logging=True,
                 model_instance_type='default', base_latency_ms='200', base_throttle_mbit='3.', min_bandwidth_mbit=0.75,
                 max_bandwidth_mbit=8., max_shift=2, buffer_inaccuarcy_s=0.5, throttle_type='selenium'):
        super().__init__(network_interface, pw, logging, model_instance_type, base_latency_ms, base_throttle_mbit,
                         min_bandwidth_mbit, max_bandwidth_mbit, max_shift, buffer_inaccuarcy_s, throttle_type)
        self.constant_bw_mbit = constant_bw_mbit

    def init_throttle(self):
        super().init_throttle()
        self.throttle(self.constant_bw_mbit)


class TCFeedbackControllerChunkSampler(TCFeedbackControllerChunk):

    def __init__(self, network_interface='wlp4s0', pw=None, logging=True, model_instance_type='default',
                 base_latency_ms='200', base_throttle_mbit='3.', min_bandwidth_mbit=0.75, max_bandwidth_mbit=8.,
                 max_shift=2, buffer_inaccuarcy_s=0.5, throttle_type='selenium'):

        super().__init__(network_interface, pw, logging, model_instance_type, base_latency_ms, base_throttle_mbit,
                         min_bandwidth_mbit, max_bandwidth_mbit, max_shift, buffer_inaccuarcy_s, throttle_type)
        self.running = False

    @abstractmethod
    def sample(self):
        pass

    def init_throttle(self):
        if not self.running:
            super().init_throttle()
            self.running = True
            self.throttle_thread = threading.Thread(target=self.__throttle_thread)
            self.throttle_thread.daemon = True
            self.throttle_thread.start()

    def __throttle_thread(self):
        while self.running:
            time_sleep, bandwidth_mbit = self.sample()
            self.throttle(bandwidth_mbit=bandwidth_mbit)
            if time_sleep > 0:
                values = list(np.arange(0, time_sleep, 5))
                if values[-1] != time_sleep:
                    values += [time_sleep]
                values = np.diff(values)
                assert sum(values) == time_sleep
                for v in values:
                    time.sleep(v)
                    if not self.running:
                        self.stop_throttle()
                        return
        self.stop_throttle()

    def stop_throttle(self):
        if self.running:
            self.running = False
            self.throttle_thread.join()
        super().stop_throttle()


class TCFeedbackControllerFile(TCFeedbackControllerChunkSampler):

    def get_trace_id(self):
        return 'file_id_%s' % self.file_paths[self.current_index].split('/')[-1]

    def __init__(self, file_paths, separator, network_interface='wlp4s0', pw=None, logging=True,
                 model_instance_type='default', base_latency_ms='200', base_throttle_mbit='3.', min_bandwidth_mbit=0.75,
                 max_bandwidth_mbit=8., max_shift=2, buffer_inaccuarcy_s=0.5, throttle_type='selenium',
                 mode='iterative'):

        super().__init__(network_interface, pw, logging, model_instance_type, base_latency_ms, base_throttle_mbit,
                         min_bandwidth_mbit, max_bandwidth_mbit, max_shift, buffer_inaccuarcy_s, throttle_type)
        self.file_paths = file_paths
        self.separator = separator
        accepted_modes = ['iterative', 'random']
        assert mode in accepted_modes, 'Choose an accepted mode from %s' % accepted_modes
        self.mode = mode
        if self.mode == 'iterative':
            self.current_index = 0
        else:
            self.current_index = np.random.randint(0, len(self.file_paths), size=1)[0]
        self.sample_counter = 0
        logger.debug('Setting {Index} and Trace {trace}'.format(Index=self.current_index,
                                                                trace=file_paths[self.current_index]))
        assert len(self.file_paths) == len(np.unique(self.file_paths)), 'Duplicate traces'
        logger.info('Loaded %d traces' % len(self.file_paths))
        self.set_sample_file(file_paths[self.current_index])

    def next_experiment(self):
        if self.mode == 'iterative':
            self.current_index += 1
            self.current_index %= len(self.file_paths)
        elif self.mode == 'random':
            self.current_index = np.random.randint(0, len(self.file_paths), size=1)[0]
        else:
            raise ValueError('Invalid sampling mode %s' % self.mode)
        self.set_sample_file(self.file_paths[self.current_index])

    def set_sample_file(self, file_path):
        self.sample_file = pd.read_csv(file_path, sep=self.separator, names=['time', 'mbit'])
        logger.info('Setting next %s traces' % file_path)
        first_time = self.sample_file.time.values[0]
        self.sample_file.time = self.sample_file.time.diff().fillna(first_time)
        self.sample_counter = 0

    def sample(self):
        time, bw = self.sample_file.iloc[self.sample_counter].values
        self.sample_counter += 1
        self.sample_counter %= len(self.sample_file)
        return time, bw


class TCFeedbackControllerRandom(TCFeedbackControllerChunkSampler):
    def get_trace_id(self):
        return '%s_%s' % (
            self.sample_t_s_arr[self.current_index_t_s], self.sample_bw_mbit_arr[self.current_index_bw_mbit])

    def __init__(self, sample_bw_mbit_arr, sample_t_s_arr, network_interface='wlp4s0', pw=None, logging=True,
                 model_instance_type='default', base_latency_ms='200', base_throttle_mbit='3.', min_bandwidth_mbit=0.75,
                 max_bandwidth_mbit=8., max_shift=2, buffer_inaccuarcy_s=0.5, throttle_type='selenium',
                 mode='iterative'):
        super().__init__(network_interface, pw, logging, model_instance_type, base_latency_ms, base_throttle_mbit,
                         min_bandwidth_mbit, max_bandwidth_mbit, max_shift, buffer_inaccuarcy_s, throttle_type)
        self.sample_t_s_arr = sample_t_s_arr
        self.sample_bw_mbit_arr = sample_bw_mbit_arr
        accepted_modes = ['iterative', 'random']
        assert mode in accepted_modes, 'Choose an accepted mode from %s' % accepted_modes
        self.mode = mode
        if self.mode == 'iterative':
            self.current_index_t_s = 0
            self.current_index_bw_mbit = 0
        else:
            self.current_index_t_s = np.random.randint(0, len(self.sample_t_s_arr), size=1)[0]
            self.current_index_bw_mbit = np.random.randint(0, len(self.sample_bw_mbit_arr), size=1)[0]
        assert hasattr(self.sample_t_s_arr[self.current_index_t_s], 'rvs'), 'only accepts my distribution class'
        assert hasattr(self.sample_bw_mbit_arr[self.current_index_bw_mbit],
                       'rvs'), 'only accepts  my distribution class'

    def next_experiment(self):
        if self.mode == 'iterative':
            if self.current_index_bw_mbit + 1 == len(self.sample_bw_mbit_arr):
                self.current_index_bw_mbit = 0
                if self.current_index_t_s + 1 == len(self.sample_t_s_arr):
                    self.current_index_t_s = 0
                else:
                    self.current_index_t_s += 1
            else:
                self.current_index_bw_mbit += 1
        else:
            self.current_index_t_s = np.random.randint(0, len(self.sample_t_s_arr), size=1)[0]
            self.current_index_bw_mbit = np.random.randint(0, len(self.sample_bw_mbit_arr), size=1)[0]

    def save_experiment(self):
        super().save_experiment()
        self.next_experiment()

    def sample(self):
        return self.sample_t_s_arr[self.current_index_t_s].rvs(), self.sample_bw_mbit_arr[
            self.current_index_bw_mbit].rvs()



