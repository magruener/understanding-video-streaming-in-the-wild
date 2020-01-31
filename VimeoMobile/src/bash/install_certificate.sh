#!/bin/bash



AVD=$1
PROXY_ADDRESS=$2
PROXY_PORT=$3
CA=$4
EMULATOR=$5
ADB=$6

appium &>/dev/null &
$EMULATOR -avd $AVD -writable-system -http-proxy $PROXY_ADDRESS:$PROXY_PORT -wipe-data  -no-window & 
$ADB wait-for-device 

A=$($ADB shell getprop sys.boot_completed | tr -d '\r')

while [ "$A" != "1" ]; do
        sleep 2
        A=$($ADB shell getprop sys.boot_completed | tr -d '\r')
done

$ADB shell input keyevent 66

$ADB root
$ADB remount






hash=$(openssl x509 -noout -subject_hash_old -in $CA)
$ADB push $CA /system/etc/security/cacerts/$hash.0
#$ADB push frida-server /data/local/tmp/
