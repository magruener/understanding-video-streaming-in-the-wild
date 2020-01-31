#!/bin/bash

adb devices | grep emulator | cut -f1 | while read line; do adb -s $line emu kill; done

pkill "shaping"
pkill "appium"
pkill "mitmdump"
pkill "node"

sleep 5
