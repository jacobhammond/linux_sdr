# linux_sdr

1. Build Project using make_project.bat
2. copy *design_1_wrapper.bit.bin* from vivado impl directory to Zybo/SD card
3. run "fpgautil -b config_codec.bit.bin"
4. run "fpgautil -b design_1_wrapper.bit.bin"
5. run "python3 sdr.py <ipaddr>

For example "python3 sdr.py 192.168.0.1" will begin the Linux SDR program and stream UDP data to 192.168.0.1 at port 25344

*IMPORTANT - The Zybo Linux image has both python2 and python3. The sdr.py software is ONLY compatible with python3. If your local environment variables are not set to use python3 as the default, you will need to call it explicitly. 