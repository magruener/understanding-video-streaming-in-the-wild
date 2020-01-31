import shutil
import argparse
import sys
import subprocess
import time
import os, signal
import pgrep
import json

MAX_WAIT = 1200
POLLING_INTERVAL = 10


def check_kill_process(pstring):
        for line in os.popen("ps ax | grep " + pstring + " | grep -v grep "):
                print("found TC process still holding")
                fields = line.split()
                pid = fields[0]
                try:
                        os.kill(int(pid), signal.SIGKILL)
                except:
                        continue
                time.sleep(3)           




def initialize_environment(provider, video_info, android_home):
        with open(video_info, "r") as fin:      
                data = json.load(fin)

        os.environ["ANDROID_HOME"] = android_home
        os.environ["CURRENT_EXPERIMENT"] = "temp_file_current_experiment"
        os.environ["CURRENT_VIDEO"] = data["video_id"]
        os.environ["PROVIDER"] = provider
        os.environ["MAX_SEGMENT"] = str(data["segment_no"])
        os.environ["KEY_SEARCH"] = data["key"]


def initialize_mitmproxy(devnull):
        
        if os.path.exists(os.environ["CURRENT_EXPERIMENT"]):
                shutil.rmtree(os.environ["CURRENT_EXPERIMENT"])
                
        cmd = 'mitmdump -s src/mitm_headers_dump.py --set block_global=false'
        subprocess.Popen([cmd], shell=True)


def check_mitmproxy_on():
        pid = True
        acc = 0
        while pid:
                pid = pgrep.pgrep("mitmdump")   
                time.sleep(POLLING_INTERVAL)
                acc += POLLING_INTERVAL
                
                if acc > MAX_WAIT:
                        print("TIMEOUT: moving anyway the files into the results")
                        return True     
        
        return True


if __name__ == "__main__":
        parser = argparse.ArgumentParser(description='GET parameters necessary to launch a video in Selenium')
        parser.add_argument('--info_file', dest='info_file', required=True)
        parser.add_argument('--launch_experiment_script', dest='script', required=True)
        parser.add_argument('--proxy-ip', dest='proxyip', required=True)
        parser.add_argument('--proxy-port', dest='proxyport', required=True)
        parser.add_argument('--avd', dest='avd', required=True)
        parser.add_argument('--provider', dest='provider', required=True)
        parser.add_argument('--dev', dest='dev', required=True)
        parser.add_argument('--directory_out', dest='out_dir', required=True)   
        parser.add_argument('--mitmproxy_ca', dest='ca', required=True)
        parser.add_argument('--android_home', dest='android_home', required=True)
        parser.add_argument('--emulator', dest='emulator', required=True)
        parser.add_argument('--adb', dest='adb', required=True)

        args = parser.parse_args()
        

        devnull = open(os.devnull, 'wb')
        
        
        try:

                print("Initializing environmental variables")
                initialize_environment(args.provider, args.info_file, args.android_home)

                
                print("Starting MITM PROXY")
                initialize_mitmproxy(devnull)
                

                print("Starting session of emulation")
                subprocess.call(["./src/bash/install_certificate.sh", args.avd, args.proxyip, args.proxyport, args.ca, args.emulator, args.adb]) 

                trace_file = os.path.join(args.out_dir, "trace")
                if not os.path.exists(trace_file):
                        print("Trace file not found")
                        sys.exit(-1)    

                check_kill_process("shaping")   
                print("Start TC")
                subprocess.Popen(["./src/bash/shaping.sh " + trace_file + " " + args.dev],shell=True, stdout=devnull, stderr=devnull)

                
                print("Starting Selenium experiment")
                cmd = 'python ' +  args.script +' --video_info ' + args.info_file +  ' --video_key_search "' + os.environ["KEY_SEARCH"] + '"'
                print(cmd)
                p = subprocess.Popen([cmd], shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, executable='/bin/bash')
                
                stdout, err = p.communicate()
                p.wait()
                rc = p.returncode
                ret = False
                timeout = False
                if rc != 0:
                        print(stdout)
                        print(err)
                        print("Failed")
                else:
                        print("Started correctly")
                        ret = check_mitmproxy_on()

                print("Cleaning processes")     

                if ret:
                        print("Experimet termianted successfully")
                        os.rename(os.environ["CURRENT_EXPERIMENT"], os.path.join(args.out_dir, "requests_log"))

        finally:
                 subprocess.call(["./src/bash/clean_processes.sh", args.adb])
                
