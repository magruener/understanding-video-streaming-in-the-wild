import logging
import os
import threading
import time

from Utility.util import get_current_unix

from TrafficController.BWEstimator import BWEstimator

LOGGING_LEVEL = logging.INFO

handler = logging.StreamHandler()
handler.setLevel(LOGGING_LEVEL)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger = logging.getLogger(__name__)
logger.setLevel(LOGGING_LEVEL)
logger.addHandler(handler)


class TCController:
    """
    Used to control the interaction between the python script and the tc shell scripts
    """

    def __init__(self,
                 policy=None,
                 network_interface='wlp4s0',
                 pw=None,
                 BW_Estimator_Rate=2.0,
                 logging=True):
        self.pw = pw
        self.dev_interface = network_interface
        self.policy = policy
        self.logging_path = 'tc_dataframe_' + policy.name
        self.tc_process = None
        self.run_calculation = False
        self.tc_path = '/sbin/tc'
        self.BW_Estimator = BWEstimator(BW_Estimator_Rate=BW_Estimator_Rate, network_interface=network_interface)
        self.logging_file = None
        self.logging = logging

    def start_BW_Estimator(self):
        self.BW_Estimator.start()

    def stop_BW_Estimator(self):
        self.BW_Estimator.stop()

    def obtain_BW_estimate(self):
        return self.BW_Estimator.obtain_estimate()

    def start_throttle_thread(self):
        """
        Starts a thread which recalculate every 3seconds the bandwidth
        """
        if not self.run_calculation:
            self.run_calculation = True
            self.init_throttle()
            self.throttle_thread = threading.Thread(target=self.throttle_routine)
            self.throttle_thread.daemon = True
            self.throttle_thread.start()

    def stop(self):
        logger.info('Stoping TC Thread')
        """
        Stops the thread
        """
        if self.run_calculation:
            self.run_calculation = False
            self.throttle_thread.join()

    def init_throttle(self):
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
            'sudo tc qdisc add dev wlp4s0 handle ffff: ingress',
            # -----------  enable the ifb interfaces:
            'sudo ifconfig ifb0 up',
            # -------- And redirect ingress traffic from the physical interfaces to corresponding ifb interface. For wlp4s0 -> ifb0:
            'sudo %s filter add dev %s parent ffff: protocol all u32 match u32 0 0 action mirred egress redirect dev ifb0' % (
            self.tc_path, self.dev_interface),
            # -------------- Limit Speed
            'sudo %s qdisc add dev ifb0 root tbf rate 1mbit latency 50ms burst 1540' % self.tc_path
        ]



        for cmd in init_throttle:
            logger.debug('Spawning %s ' % cmd)
            # os.popen("sudo -S %s" % (cmd), 'w').write(self.pw)

            os.system('echo %s|sudo -S %s' % (self.pw, cmd))

    def set_logging_path(self, path_name):
        self.logging_path = path_name

    def throttle_routine(self):
        """
        Contains the routine which continously samples from the policy
        :return:
        """
        while self.run_calculation:
            time_sleep, bw = self.policy.sample()
            self.throttle(bandwidth=bw, duration=time_sleep)

        self.stop_throttle()

    def throttle(self, bandwidth, duration):
        """
        :param bandwidth: bandwidth in mbit to which we want to restrict the download speed
        :param duration: duration of the limitation
        :return:
        """
        if self.logging_file is None and self.logging:
            self.logging_file = open(self.logging_path, 'w')
        throttle_cmd = 'sudo %s qdisc change dev ifb0 root tbf rate %.5fmbit latency 50ms burst 1540'
        cmd = throttle_cmd % (self.tc_path, bandwidth)
        logger.debug('Spawning %s' % cmd)
        # os.popen("sudo -S %s" % (cmd), 'w').write(self.pw)

        os.system('echo %s | sudo -S %s' % (self.pw, cmd))
        time.sleep(duration)
        logging_output = '%.3f\t%.3f\n' % (get_current_unix(), bandwidth)
        self.logging_file.write(logging_output)
        logger.debug('Writing %s' % logging_output)

    def stop_throttle(self):
        if self.logging_file is not None:
            self.logging_file.close()
            self.logging_file = None
        cleanup_cmd = ['sudo %s qdisc del dev %s ingress' % (self.tc_path, str(self.dev_interface)),
                       'sudo %s qdisc del dev ifb0 root' % self.tc_path]
        # ------------------------------ Better be save than sorry, we delete all rules imposed by tc
        for cmd in cleanup_cmd:
            logger.debug(cmd)
            #os.popen("sudo -S %s" % (cmd), 'w').write(self.pw)
            os.system('echo %s|sudo -S %s' % (self.pw, cmd))
