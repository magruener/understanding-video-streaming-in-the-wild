#!/bin/bash
ADB=$1

$ADB devices | grep emulator | cut -f1 | while read line; do $ADB -s $line emu kill; done

pkill "shaping"
pkill "appium"
pkill "mitmdump"
pkill "node"

sleep 5
