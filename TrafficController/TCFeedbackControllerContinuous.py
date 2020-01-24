import logging
from abc import ABC

import numpy as np
import pandas as pd

from TrafficController.TCFeedbackControllerChunk import TCFeedbackControllerChunk, \
    TCFeedbackControllerFile, TCFeedbackControllerChunkConstant

LOGGING_LEVEL = logging.DEBUG

handler = logging.StreamHandler()
handler.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
logger.addHandler(handler)


class TCFeedbackControllerContinuous(TCFeedbackControllerChunk, ABC):

    def __init__(self, network_interface='wlp4s0', pw=None, logging=True, model_instance_type='default',
                 base_latency_ms='200', base_throttle_mbit='3.', min_bandwidth_mbit=0.75, max_bandwidth_mbit=8.,
                 max_shift=2, buffer_inaccuarcy_s=2., throttle_type='selenium'):

        super().__init__(network_interface, pw, logging, model_instance_type, base_latency_ms, base_throttle_mbit,
                         min_bandwidth_mbit, max_bandwidth_mbit, max_shift, buffer_inaccuarcy_s, throttle_type)


    def set_video_information(self, path_video_id):
        logger.info('Setting new Video %s' % path_video_id)
        super().set_video_information(path_video_id=path_video_id)
        self.load_range_mapper(path_video_id=path_video_id)

    def load_range_mapper(self, path_video_id):
        path_to_csv = path_video_id + '_video_info_range_mapper'
        logger.debug('Loading %s as range mapper' % path_video_id)
        self.range_mapper = pd.read_csv(path_to_csv, index_col=0)
        self.range_mapper['quality_level'] = self.range_mapper.reset_index()['itag'].map({v: k for k, v in enumerate(
            self.range_mapper.groupby('itag').mean().sort_values('vmaf_score').index.values)}).astype(int).values
        self.quality_byte_mapper = {k: group.byterange.sort_values().values for k, group in self.range_mapper.groupby(
            'quality_level')}
        logger.debug('Available quality levels %s' % self.quality_byte_mapper.keys())
        self.range_mapper = self.range_mapper.reset_index().set_index(['byterange', 'quality_level'])

    def map_byte_to_time(self, byte, quality_level):
        closest_index = np.searchsorted(self.quality_byte_mapper[quality_level], byte)
        closest_value = self.quality_byte_mapper[quality_level][closest_index]
        return self.range_mapper.loc[(closest_value, quality_level)].time_s

    def parse_newly_downloaded(self, newly_downloaded):
        parsed_entry_index = 0
        while parsed_entry_index < len(newly_downloaded):
            parsed_entry = newly_downloaded[parsed_entry_index]
            quality_level_chosen = self.video_quality_mapper.contained_in_url.map(lambda cnt_url: sum(
                [True if c in parsed_entry['url'] else False for c in cnt_url]) > 0)
            if sum(quality_level_chosen.values) != 1:
                logger.debug(parsed_entry['n_segment'])
                newly_downloaded.remove(parsed_entry)
                continue
            quality_level_chosen = self.video_quality_mapper.quality_level[quality_level_chosen].values[0]
            if parsed_entry['byte_end'] >= self.quality_byte_mapper[quality_level_chosen][-1]:
                logger.debug('File is over the playing limit. Were ignoring it')
                newly_downloaded.remove(parsed_entry)
                logger.debug('Removed wrongly formatted entry, we still have %d entries' % len(newly_downloaded))
                continue
            parsed_entry_index += 1
            parsed_entry['quality_level_chosen'] = quality_level_chosen
            parsed_entry['t_start'] = np.around(self.map_byte_to_time(parsed_entry['byte_start'], quality_level_chosen),
                                                2)
            parsed_entry['t_end'] = np.around(self.map_byte_to_time(parsed_entry['byte_end'], quality_level_chosen), 2)
            parsed_entry['seg_len_s'] = parsed_entry['t_end'] - parsed_entry['t_start']
            n_segment = np.searchsorted(self.video_information_csv.time_s, parsed_entry['t_start'])
            parsed_entry['n_segment'] = n_segment
            parsed_entry['bitrate_level'] = self.bitrate_match.iloc[n_segment].values[quality_level_chosen]
            parsed_entry['vmaf_level'] = self.vmaf_match.iloc[n_segment].values[quality_level_chosen]


class TCFeedbackControllerContinuousConstant(TCFeedbackControllerChunkConstant, TCFeedbackControllerContinuous):
    pass

class TCFeedbackControllerContinuousFile(TCFeedbackControllerFile, TCFeedbackControllerContinuous):
    pass

