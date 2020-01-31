.PHONY: all
SHELL := /bin/bash


# DIRECTORIES SETUP:
#
#

main_results_dir = results
traces_dir = resources/traces/PAMTrace
video_list = resources/lists/VimeoVideoList
key_search = resources/lists/VideoKeySearch
info_dir = resources/video_info


# MACHINE SETUP:
#
#

proxy_ip = 192.168.178.80
proxy_port = 8080
dev = enp0s31f6


# EXPERIMENT SETUP
#
#

avd_name = pixel
provider_name = Vimeo
ca=~/.mitmproxy/mitmproxy-ca-cert.pem # PATH TO MITM PROXY
android_home = ~/Android/Sdk/ # ANDROID HOME
adb = ~/Android/Sdk/platform-tools/adb
emulator = ~/Android/Sdk/emulator/emulator



# remember to change the subpath element according to your filesystem (in my case is the 4th) 
#
get_tracename = $(word 4, $(subst /, , $(1)))
traces =  $(wildcard $(traces_dir)/*)

targets =  $(foreach t, $(traces), $(main_results_dir)/$(call get_tracename, $t)/requests_log/) $(foreach t, $(traces), $(main_results_dir)/$(call get_tracename, $t)/video_info) $(foreach t, $(traces), $(main_results_dir)/$(call get_tracename, $t)/info) $(foreach t, $(traces), $(main_results_dir)/$(call get_tracename, $t)/video_mapping) 

all: ${targets}


$(main_results_dir)/%/requests_log/:  $(main_results_dir)/%/video_info $(main_results_dir)/%/info $(main_results_dir)/%/video_mapping #: -> dependency on the sources	
	
	mkdir -p $(main_results_dir)/$*/
	python3 src/single_experiment.py\
					--info_file  $(main_results_dir)/$*/info\
				  --launch_experiment_script src/vimeo_mobile_test.py\
					--proxy-ip $(proxy_ip)\
					--proxy-port $(proxy_port)\
					--avd $(avd_name)\
					--provider $(provider_name)\
					--dev $(dev)\
					--directory_out $(main_results_dir)/$*/\
					--mitmproxy_ca $(ca)\
					--android_home $(android_home)\
					--emulator $(emulator)\
					--adb $(adb)
	
$(main_results_dir)/%/video_info $(main_results_dir)/%/info $(main_results_dir)/%/video_mapping:  
	mkdir -p $(main_results_dir)/$*/
	python3	src/find_video_info.py\
					--keyfile $(key_search)\
					--trace $*\
					--trace-dir $(traces_dir)\
					--video-list $(video_list)\
					--info-dir $(info_dir)\
				 	--out  $(main_results_dir)/$*/video_info

clean:
	@echo "Removing old experiments"
	rm -r -f $(main_results_dir)/

