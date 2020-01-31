#!/bin/bash


#Traffic shaper TC:
#Read a trace .txt file in the form of:

#Time_1 Bw_1
#Time_2 Bw_2
#Time_3 Bw_3

#Time: float, interpreted as seconds
#Bw: float, interpreted as mbit

#Shape the bw according to the trace file. When the file ends, it starts again.
#PARAMETERS:
#1) Trace file path
#2) Dev interface to manipulate (retieve the name with "ifconfig" command)


# Terminate -> CTRL + C


# Name of the traffic control command.
TC=/sbin/tc
MBS="mbit"
MS="ms"
M="mbit"
PI="3.14"
LATENCY_MAX="200"
BURST="1540"
MIN="0.1"

start() {
	sudo  modprobe ifb
	sudo  ip link set dev ifb0 up
	sudo $TC qdisc add dev $IF ingress
	sudo $TC filter add dev $IF parent ffff: protocol ip u32 match u32 0 0  action mirred egress redirect dev ifb0
	sudo $TC qdisc add dev ifb0 root handle 1: prio priomap 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
	sudo $TC qdisc add dev ifb0 parent 1:2 handle 2: tbf rate $RATE$MBS latency $LATENCY_MAX$MS burst $BURST
	sudo $TC filter add dev ifb0 parent 1:0 protocol ip u32 match ip sport 443 0xffff flowid 1:2 
}
stop() {
    
    echo "Stopping TC"
    sudo $TC qdisc del dev $IF ingress
    sudo $TC qdisc del dev ifb0 root
    exit
}


reset()
{
    echo "Resetting"
    sudo $TC qdisc del dev $IF ingress
    sudo $TC qdisc del dev ifb0 root
    
}


modify(){
	sudo $TC qdisc change dev ifb0 parent 1:2 handle 2: tbf rate $RATE$MBS latency $LATENCY_MAX$MS burst $BURST

}


if [ "$#" -le 1 ]; then
	echo "USAGE: <FILENAME> <DEV_INTERFACE>"
	exit
fi

trap stop SIGTERM SIGINT


filename="$1"
IF="$2"
RATE="1"
echo "Starting " + $filename


reset
start
offset=0


while true
do
	time_now=0
	while read -r line
	do
		name="$line"
		set -f; IFS=' '
		set -- $line
		time=$1; bw=$2
		set +f; unset IFS

		time_to_sleep=$( echo "($time-$time_now)" | bc -l )
		sleep $time_to_sleep
		time_now=$time
		
		if (( $(echo "$bw > $MIN" |bc -l) )); then
			RATE=$bw
		else
			RATE=$MIN
		fi
		timestamp=$( echo "($time+$offset)" | bc -l )
		modify
	
	done < "$filename"
	offset=$( echo "($offset+$time_now)" | bc -l )
done

echo "Stopping"
stop
