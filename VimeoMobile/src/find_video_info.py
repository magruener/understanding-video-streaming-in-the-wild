import argparse
import json
import glob
from os import path, rename
import shutil
import pandas as pd


# CREATES THE PRELIMINARY FILES NEEDED TO RUN AN EXPERIMENT


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find the corresponding file trace")
    parser.add_argument("--trace", dest="trace", required=True)
    parser.add_argument("--trace-dir", dest="trace_dir", required=True)
    parser.add_argument("--video-list", dest="video_list", required=True)
    parser.add_argument("--info-dir", dest="info", required=True)
    parser.add_argument("--out", dest="out", required=True)
    parser.add_argument("--keyfile", dest="key_file",required=True)   
    args = parser.parse_args()

    list_of_traces = [path.basename(x) for x in glob.glob(path.join(args.trace_dir, "*"))]
    list_of_traces.sort()
    index = list_of_traces.index(args.trace)

    with open(args.video_list) as f:
        file_list = f.readlines()
    

    url = file_list[index]
    video_id = url.split('/')[-1].strip()

    files_to_move = [x for x in glob.glob(path.join(args.info, '*')) if video_id in x and "mapper" in x]
    file_to_move = files_to_move[0]

    shutil.copy(file_to_move, args.out)
    shutil.copy(path.join(args.trace_dir, args.trace), path.join(path.dirname(args.out), "trace"))

    info_file = path.join(path.dirname(args.out), "info")
    segment_file = [x for x in glob.glob(path.join(args.info, '*')) if video_id in x and "_video_info" in x]    
    shutil.copy(segment_file[0], path.join(path.dirname(args.out), "video_mapping"))
   
    csv = pd.read_csv(segment_file[0])

    number_of_segments = len(list(csv["delta_t_s"]))

    with open(args.key_file, "r") as keyfile:
       keys = keyfile.readlines()

    search_key = ""
    for key in keys:
       if video_id in key:
           search_key = key.split("_")[1].strip()
           break


    
    prop = {}
    prop["video_id"] = video_id
    prop["trace"] = args.trace
    prop["segment_no"] = number_of_segments    
    prop["key"] = search_key
    
    
    
    with open(info_file, "w") as fout:
    	json.dump(prop, fout)
