compile:
	arduino-cli compile --fqbn esp32:esp32:XIAO_ESP32C6 ../esp32thermometer 

upload:
	arduino-cli upload ../esp32thermometer -p /dev/ttyACM0 --fqbn esp32:esp32:XIAO_ESP32C6

u: upload
c: compile

label:
	cd label && latexmk -xelatex -g label.tex && cd ..

view:
	xreader label/label.pdf &
