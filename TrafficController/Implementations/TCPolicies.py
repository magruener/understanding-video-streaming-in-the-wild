import numpy as np
import pandas as pd

from TrafficController.Interfaces.TCPolicy import TCPolicy


class TCControllerFilePolicy(TCPolicy):
    """
    Load the file given and adapts its policy according to that
    """

    def __init__(self, name, file, sep):
        super().__init__(name)
        self.sample_file = pd.read_csv(file, sep=sep, names=['time', 'mbit'])
        self.sample_counter = 0
        self.time_now = 0
        self.name = name

    def sample(self):
        time, bw = self.sample_file.iloc[self.sample_counter].values
        self.sample_counter += 1
        self.sample_counter %= len(self.sample_file)
        if self.time_now >= time:
            # We start from the beginning
            self.time_now = 0
        time_return = time - self.time_now
        self.time_now = time
        return time_return, bw


class TCControllerRandomPolicy(TCPolicy):
    """
    Randomly samples the bandwidth and duration of the constraint within the given boundaries
    """

    def __init__(self, name, ceil_bw, floor_bw, floor_duration, ceil_duration):
        super().__init__(name)
        self.ceil_bw = ceil_bw
        self.floor_bw = floor_bw
        self.ceil_duration = ceil_duration
        self.floor_duration = floor_duration

        self.name = name

    def sample(self):
        bw = np.random.uniform(self.floor_bw, self.ceil_bw)
        time_return = np.random.uniform(self.floor_duration, self.ceil_duration)
        return time_return, bw


class TCControllerConstantPolicy(TCPolicy):
    """
    Always returns the same duration and bandwidth
    """

    def __init__(self, name, constant_time, constant_bw):
        super().__init__(name)
        self.constant_bw = constant_bw
        self.constant_time = constant_time
        self.name = name

    def sample(self):
        return self.constant_time, self.constant_bw
