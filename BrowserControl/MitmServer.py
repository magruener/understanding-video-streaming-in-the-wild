import json
import os
import platform
import subprocess
import threading


class MitMServer:

    def __init__(self, path='browsermob-proxy', options=None):
        """
        Initialises a Server object

        :param str path: Path to the browsermob proxy batch file
        :param dict options: Dictionary that can hold the port.
            More items will be added in the future.
            This defaults to an empty dictionary
        """
        self.options = options if options is not None else {}

        path_var_sep = ':'
        if platform.system() == 'Windows':
            path_var_sep = ';'

        exec_not_on_path = True
        for directory in os.environ['PATH'].split(path_var_sep):
            if os.path.isfile(os.path.join(directory, path)):
                exec_not_on_path = False
                break

        if not os.path.isfile(path) and exec_not_on_path:
            raise ValueError("Mitm-Proxy binary couldn't be found "
                             "in path provided: %s" % path)

        self.path = path
        self.host = 'localhost'
        self.port = options.get('port', 8080)
        self.process = None

        if platform.system() == 'Darwin':
            self.command = ['sh']
        else:
            self.command = []

        self.command += [path, '-p %s' % self.port] #, #'-s %s' % path.replace('mitmdump', 'har_dump.py'),'--set hardump=./dummy_file.har']
        self.proxy = 'localhost:%d' % self.port
        self.har = {'log': {'entries': []}}
        self.is_active = False
        self.parser_thread = None

    def new_har(self,options = None):
        self.__stop()
        self.is_active = True
        self.__start()

    def continous_parse(self):
        with open('dummy_file.har', 'r') as json_parsed:
            while self.is_active:
                try:
                    self.har = json.load(json_parsed)
                except:
                    pass

    def __start(self):
        """
        This will start the browsermob proxy and then wait until it can
        interact with it

        :param dict options: Dictionary that can hold the path and filename
            of the log file with resp. keys of `log_path` and `stdout_log_file`
        """
        if self.options is None:
            options = {}
        log_path = self.options.get('log_path', os.getcwd())
        stdout_log_file = self.options.get('stdout_log_file', 'stdout_server.log')
        stderr_log_file = self.options.get('stderr_log_file', 'stderr_server.log')

        stdout_log_file = os.path.join(log_path, stdout_log_file)
        stderr_log_file = os.path.join(log_path, stderr_log_file)


        self.stdout_log_file = open(stdout_log_file, 'w')
        self.stderr_log_file = open(stderr_log_file, 'w')

        self.process = subprocess.Popen(self.command,
                                        stdout=self.stdout_log_file,
                                        stderr=self.stderr_log_file)
        self.parser_thread = threading.Thread(target=self.continous_parse)
        self.parser_thread.daemon = True
        self.parser_thread.start()

    def __stop(self):
        """
        This will stop the process running the proxy
        """
        self.is_active = False
        if self.parser_thread is None:
            return
        self.parser_thread.join(timeout=15)
        if self.process.poll() is not None:
            return
        try:
            self.process.kill()
            self.process.wait()
        except AttributeError:
            # kill may not be available under windows environment
            pass
        self.stdout_log_file.close()
        self.stderr_log_file.close()
        os.remove('./dummy_file.har')
