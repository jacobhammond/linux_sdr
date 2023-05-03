# Program: sdr.py
# Author: Jacob Hammond
# Date: 04/27/2023
#
# NOTE: THIS IS A *PYTHON3* PROGRAM ONLY
#
# Description: This is the Full Radio Peripheral Linux Lab Program. It provides
# a terminal-based UI for the user to tune the radio frequencies and streams the
# output data to the DAC interface and over UDP.
#
# Instructions:    run "python3 sdr.py <ip_destination_address>"
# For example:
# "python3 sdr.py 192.168.0.1"
# will begin the program and start streaming UDP packets to the given IP address at port 25344
#!/usr/bin/env python3
import mmap
import math
import struct
import socket
import sys
import os
import threading
import termios
import tty

FIFO_PERIPH_ADDRESS = 0x43c10000
FIFO_CAPACITY_OFFSET = 0x0
FIFO_DATA_OFFSET = 0x4

RADIO_TUNER_FAKE_ADC_PINC_OFFSET = 0x0
RADIO_TUNER_TUNER_PINC_OFFSET = 0x4
RADIO_TUNER_CONTROL_REG_OFFSET = 0x8
RADIO_TUNER_TIMER_REG_OFFSET = 0xC
RADIO_PERIPH_ADDRESS = 0x43c00000

tfreq = 30000000
freq = 30001000
ip_addr = sys.argv[1]
    
def print_menu():
    print("\r\nPress 't' to tune radio to a new frequency\r\nPress 'f' to tune to set the fake ADC to a new frequency\r\nPress 'e' to toggle Ethernet Streaming\r\nPress 'U/u' to increase fake ADC frequency by 1000/100 Hz\r\nPress 'D/d' to decrease fake ADC frequency by 1000/100 Hz\r\nPress 'q' to quit\r\nPress [space] to repeat this menu\r\n\n")

def set_freq():
    global radio
    i = 0
    print("Enter a frequency in Hz: ")
    freq_string = input()
    freq_string.replace('\r', '')
    return(int(freq_string))

def step_freq(setting):
    global freq
    if setting == 0:
        freq += 100
    elif setting == 1:
        freq += 1000
    elif setting == 2:
        freq -= 100
    elif setting == 3:
        freq -= 1000
    if freq < 0:
        print("\t*Frequency cannot be set less than zero. Setting to zero\r\n")
        freq = 0
    radioTuner_setAdcFreq(radio, 0)

def get_mem_object(addr):
    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    mem = mmap.mmap(fd, 4096, offset=addr)
    os.close(fd)
    return mem

def read_fifo_cap(mem):
    mem.seek(FIFO_CAPACITY_OFFSET)
    data = mem.read(4)
    capacity = int.from_bytes(data, "little")
    return capacity

def read_fifo_data(mem):
    mem.seek(FIFO_DATA_OFFSET)
    data = mem.read(4)
    return data

def read_timer(mem):
    mem.seek(RADIO_TUNER_TIMER_REG_OFFSET)
    data = mem.read(4)
    time = int.from_bytes(data, "little")
    return time

def radioTuner_tuneRadio(mem, setting):
    global tfreq
    if (setting == 1):
      tfreq = set_freq()
    pinc = int(1*tfreq*(2**27)/125.0e6)
    mem.seek(RADIO_TUNER_TUNER_PINC_OFFSET)
    mem.write(struct.pack('i',int(pinc)))
    string = f"Tuner DDS Phase Increment: {pinc}\nTuned Radio to: {tfreq} Hz\n"
    print(string)
     
def radioTuner_setAdcFreq(mem, setting):
    global freq
    if (setting == 1):
      freq = set_freq()
    pinc = int(freq*(2**27)/125.0e6)
    mem.seek(RADIO_TUNER_FAKE_ADC_PINC_OFFSET)
    mem.write(struct.pack('i',int(pinc)))
    string = f"Fake ADC Phase Increment: {pinc}\nFake ADC Tuned to: {freq} Hz\n"
    print(string)

def getch():
    """Read a single character from the terminal without echoing."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        char = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return char

def radio_reset(mem, setting):
    mem.seek(RADIO_TUNER_CONTROL_REG_OFFSET)
    if(setting == 1):
        mem.write(struct.pack('i',1))
    else:
        mem.write(struct.pack('i',0))

def cleanup():
    global s
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    radio_reset(radio, 1)

def swap_pairs(byte_array):
    for i in range(0, len(byte_array) - 1, 2):
        byte_array[i], byte_array[i + 1] = byte_array[i + 1], byte_array[i]
    return byte_array

def ui():
    menu_select = ""
    global stop_threads
    global stop_udp
    global radio
    global fifo
    radio_reset(radio, 0)
    radioTuner_tuneRadio(radio, 0)
    radioTuner_setAdcFreq(radio, 0)
        
    #print welcome message
    print("\nWelcome to Linux SDR with Ethernet by Jacob Hammond\n")
    print_menu()
    print("Ethernet Streaming Enabled.\r\n")
    
    #UI Thread
    while True:
        if stop_threads:
          break
        menu_select = getch()
        if menu_select == 't':
            radioTuner_tuneRadio(radio, 1)
        elif menu_select == 'f':
            radioTuner_setAdcFreq(radio, 1)
        elif menu_select == 'u':
            step_freq(0)
        elif menu_select == 'U':
            step_freq(1)
        elif menu_select == 'd':
            step_freq(2)
        elif menu_select == 'D':
            step_freq(3)
        elif menu_select == ' ':
            print_menu()
        elif menu_select == 'q':
            print("Program Terminated")
            cleanup()
            stop_threads = True
        elif menu_select == 'e':
            stop_udp = not(stop_udp)
            if stop_udp:
                toggle = "Disabled"
            else:
                toggle = "Enabled"
            print(f"Ethernet Streaming {toggle}.\r\n")
            
        else:
            # invalid/try again
            print("Invalid input, try again.\n")

def udp():      
    #FIFO UDP Thread
    global stop_udp
    global stop_threads
    global radio
    global fifo
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = 25344
    data = bytearray(b'.\x00\x00')
    sample = bytearray()
    while True:
        if stop_threads:
            s.close()
            break
        start_time = read_timer(radio)
        if(read_fifo_cap(fifo) > 255):
            for i in range(256):
                sample.extend(read_fifo_data(fifo))
            #Send UDP Packet
            sample = swap_pairs(bytearray(sample))
            data.extend(sample)
            data.pop()
            while(abs(read_timer(radio) - start_time) < 2604): #125MHz/48kHz = 2604.17
                pass
            if not stop_udp:
                s.sendto(data, (ip_addr, port))
            #update packet counter
            if(data[0] != 0xff):
                data[0] = data[0] + 1
            else:
                data[0] = 0x00
                data[1] = data[1] + 1
            #clear old data, from packet
            del data[3:]
            sample.clear()


if __name__ == "__main__":
    #init memory objects
    radio = get_mem_object(RADIO_PERIPH_ADDRESS)
    fifo = get_mem_object(FIFO_PERIPH_ADDRESS)
    #create threads
    stop_threads = False
    stop_udp = False
    t1 = threading.Thread(target=ui)
    t2 = threading.Thread(target=udp)
    #start threads
    t1.start()
    t2.start()
    #wait until all threads finish
    t1.join()
    t2.join()
