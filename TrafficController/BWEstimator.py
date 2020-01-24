import threading
import time
from collections import deque

import psutil


class BWEstimator:
    """
    Reads out the received and sent bytes from the given interface
    """

    def __init__(self, BW_Estimator_Rate=3, network_interface='wlp4s0'):
        self.dt = BW_Estimator_Rate
        self.interface = network_interface
        self.transfer_rate_queue = deque(maxlen=3)
        self.run_calculation = False

    def stop(self):
        """
        Stops the thread
        """
        if self.run_calculation:
            self.run_calculation = False
            self.t.join()

    def start(self):
        """
        Starts a thread which recalculate every 3seconds the bandwidth
        """
        if not self.run_calculation:
            self.t = threading.Thread(target=self.calculate_download_speed)
            self.run_calculation = True
            self.t.start()

    def obtain_estimate(self):
        try:
            return self.transfer_rate_queue[-1]
        except:
            return -1

    def calculate_download_speed(self):
        """
        Simple download speed calculation
        """
        # https://stackoverflow.com/questions/21866951/get-upload-download-kbps-speed

        last_download_counter = psutil.net_io_counters(pernic=True)[self.interface].bytes_recv

        while self.run_calculation:
            time.sleep(self.dt)
            current_download_counter = psutil.net_io_counters(pernic=True)[self.interface].bytes_recv
            download_rate = float(current_download_counter - last_download_counter) / self.dt  # bytes/s
            download_rate *= 8e-6  # to mbit/s
            if download_rate > .1:
                self.transfer_rate_queue.append(download_rate)
                last_download_counter = current_download_counter

    def print_rate(self):
        try:
            print('DL: %.3f mbit/s' % self.transfer_rate_queue[-1])
        except IndexError:
            print('DL: - mbit/s')
