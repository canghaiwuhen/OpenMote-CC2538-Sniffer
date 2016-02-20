#!/usr/bin/env python

import serial
import struct
import os
import sys
import glob
import fcntl
import subprocess
import time
import platform
import array
import subprocess

lut = [
    0x0000, 0x1189, 0x2312, 0x329B, 0x4624, 0x57AD, 0x6536, 0x74BF,
    0x8C48, 0x9DC1, 0xAF5A, 0xBED3, 0xCA6C, 0xDBE5, 0xE97E, 0xF8F7,
    0x1081, 0x0108, 0x3393, 0x221A, 0x56A5, 0x472C, 0x75B7, 0x643E,
    0x9CC9, 0x8D40, 0xBFDB, 0xAE52, 0xDAED, 0xCB64, 0xF9FF, 0xE876,
    0x2102, 0x308B, 0x0210, 0x1399, 0x6726, 0x76AF, 0x4434, 0x55BD,
    0xAD4A, 0xBCC3, 0x8E58, 0x9FD1, 0xEB6E, 0xFAE7, 0xC87C, 0xD9F5,
    0x3183, 0x200A, 0x1291, 0x0318, 0x77A7, 0x662E, 0x54B5, 0x453C,
    0xBDCB, 0xAC42, 0x9ED9, 0x8F50, 0xFBEF, 0xEA66, 0xD8FD, 0xC974,
    0x4204, 0x538D, 0x6116, 0x709F, 0x0420, 0x15A9, 0x2732, 0x36BB,
    0xCE4C, 0xDFC5, 0xED5E, 0xFCD7, 0x8868, 0x99E1, 0xAB7A, 0xBAF3,
    0x5285, 0x430C, 0x7197, 0x601E, 0x14A1, 0x0528, 0x37B3, 0x263A,
    0xDECD, 0xCF44, 0xFDDF, 0xEC56, 0x98E9, 0x8960, 0xBBFB, 0xAA72,
    0x6306, 0x728F, 0x4014, 0x519D, 0x2522, 0x34AB, 0x0630, 0x17B9,
    0xEF4E, 0xFEC7, 0xCC5C, 0xDDD5, 0xA96A, 0xB8E3, 0x8A78, 0x9BF1,
    0x7387, 0x620E, 0x5095, 0x411C, 0x35A3, 0x242A, 0x16B1, 0x0738,
    0xFFCF, 0xEE46, 0xDCDD, 0xCD54, 0xB9EB, 0xA862, 0x9AF9, 0x8B70,
    0x8408, 0x9581, 0xA71A, 0xB693, 0xC22C, 0xD3A5, 0xE13E, 0xF0B7,
    0x0840, 0x19C9, 0x2B52, 0x3ADB, 0x4E64, 0x5FED, 0x6D76, 0x7CFF,
    0x9489, 0x8500, 0xB79B, 0xA612, 0xD2AD, 0xC324, 0xF1BF, 0xE036,
    0x18C1, 0x0948, 0x3BD3, 0x2A5A, 0x5EE5, 0x4F6C, 0x7DF7, 0x6C7E,
    0xA50A, 0xB483, 0x8618, 0x9791, 0xE32E, 0xF2A7, 0xC03C, 0xD1B5,
    0x2942, 0x38CB, 0x0A50, 0x1BD9, 0x6F66, 0x7EEF, 0x4C74, 0x5DFD,
    0xB58B, 0xA402, 0x9699, 0x8710, 0xF3AF, 0xE226, 0xD0BD, 0xC134,
    0x39C3, 0x284A, 0x1AD1, 0x0B58, 0x7FE7, 0x6E6E, 0x5CF5, 0x4D7C,
    0xC60C, 0xD785, 0xE51E, 0xF497, 0x8028, 0x91A1, 0xA33A, 0xB2B3,
    0x4A44, 0x5BCD, 0x6956, 0x78DF, 0x0C60, 0x1DE9, 0x2F72, 0x3EFB,
    0xD68D, 0xC704, 0xF59F, 0xE416, 0x90A9, 0x8120, 0xB3BB, 0xA232,
    0x5AC5, 0x4B4C, 0x79D7, 0x685E, 0x1CE1, 0x0D68, 0x3FF3, 0x2E7A,
    0xE70E, 0xF687, 0xC41C, 0xD595, 0xA12A, 0xB0A3, 0x8238, 0x93B1,
    0x6B46, 0x7ACF, 0x4854, 0x59DD, 0x2D62, 0x3CEB, 0x0E70, 0x1FF9,
    0xF78F, 0xE606, 0xD49D, 0xC514, 0xB1AB, 0xA022, 0x92B9, 0x8330,
    0x7BC7, 0x6A4E, 0x58D5, 0x495C, 0x3DE3, 0x2C6A, 0x1EF1, 0x0F78
]

HDLC_FLAG        = 0x7E
HDLC_ESCAPE      = 0x7D
HDLC_ESCAPE_MASK = 0x20

platform = platform.system()
ser = serial.Serial()
pipe = None

def pickSerialPort():
    ports = []
    if platform == 'Windows':
        import _winreg as winreg
        path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        for i in range(winreg.QueryInfoKey(key)[1]):
            try:
                val = winreg.EnumValue(key,i)
                if val[0].find('VCP') > -1:
                    ports.append(str(val[1]))
            except:
                pass
    elif platform == 'Darwin':
        ports = [port for port in glob.glob('/dev/tty.usbserial*')]
    elif platform == 'Linux':
        ports = [port for port in glob.glob('/dev/ttyUSB*')]
    else:
        raise RuntimeError('Unsupported OS')

    if len(ports) == 0:
        print("No serial ports found!")
        return None
    elif len(ports) == 1:
        print("Using serial port '" + str(ports[0]) + "'")
        return ports[0]
    else:
        ports = sorted(ports)
        while (True):
            try:
                print("Multiple serial ports were found:")
                for i in range(len(ports)):
                    print("- [" + str(i) + "] " + str(ports[i]))
                selectedPort = int(input("Choose your serial port: "))
                if selectedPort < 0 or selectedPort >= len(ports):
                    print("Input number is outside bounds!")
                    continue
                else:
                    return ports[selectedPort]
            except (KeyboardInterrupt):
                return None
            except:
                print("Input parameter is not a number!")
                continue

def createPipe(name):
    if platform == 'Linux' or platform == 'Darwin':
        if os.path.exists(name):
            response = str(input('File ' + name + ' already exists. Delete it and continue? [y/N] '))
            if response == 'y' or response == 'Y':
                os.remove(name)
            else:
                quit()

        os.mkfifo(name)
    elif platform == 'Windows':
        raise RuntimeError('Pipe is not yet implemented on windows')
    else:
        raise RuntimeError('Unsupported OS')

def removePipe(name):
    if platform == 'Linux' or platform == 'Darwin':
        os.remove(name)
    elif platform == 'Windows':
        raise RuntimeError('Pipe is not yet implemented on windows')
    else:
        raise RuntimeError('Unsupported OS')

def calcCRC(string):
    crc = 0xFFFF
    for c in string:
        crc = lut[ord(c) ^ ((crc >> 8) & 0xFF)] ^ ((crc << 8) & 0xFFFF)
    return crc;

def decode(msg, quiet=False):
    escaped = False
    string = ''
    for c in msg:
        if ord(c) == HDLC_ESCAPE:
            escaped = True
            continue
        else:
            if escaped:
                string += chr(ord(c) ^ HDLC_ESCAPE_MASK)
                escaped = False
            else:
                string += c

    if len(string) < 7:
        if not quiet:
            print("WARNING: Received string too short")
        return ('', 0)

    if calcCRC(string[:-2]) != ((ord(string[-2]) << 8) + ord(string[-1])):
        if not quiet:
            print("WARNING: CRC check failed!")
        return ('', 0)

    return (string[:-2], (ord(string[-2]) << 8) + ord(string[-1]))


def encode(string):
    crc = calcCRC(string)

    byteArray = bytearray()
    byteArray.append(HDLC_FLAG)
    for c in string:
        if ord(c) == HDLC_FLAG or ord(c) == HDLC_ESCAPE:
            byteArray.append(HDLC_ESCAPE)
            byteArray.append(ord(c) ^ HDLC_ESCAPE_MASK)
        else:
            byteArray.append(ord(c))

    crcByte = (crc >> 8) & 0xFF
    if crcByte == HDLC_FLAG or crcByte == HDLC_ESCAPE:
        byteArray.append(HDLC_ESCAPE)
        byteArray.append(crcByte ^ HDLC_ESCAPE_MASK)
    else:
        byteArray.append(crcByte)

    crcByte = (crc >> 0) & 0xFF
    if crcByte == HDLC_FLAG or crcByte == HDLC_ESCAPE:
        byteArray.append(HDLC_ESCAPE)
        byteArray.append(crcByte ^ HDLC_ESCAPE_MASK)
    else:
        byteArray.append(crcByte)

    byteArray.append(HDLC_FLAG)
    return byteArray


def pickRadioChannel():
    channel = 0
    while channel < 11 or channel > 26:
        try:
            channel = int(input("Select the IEEE 802.15.4 channel number (11-26): "))
        except (KeyboardInterrupt):
            return None
        except:
            pass

    print('Setting radio channel to ' + str(channel))
    return channel

def program(channel):
    word = ''
    count = 0
    totalCount = 0
    unackedByteCount = 0
    lastIndex = 0
    lastSeqNr = -1
    expectedSeqNr = 1
    receiving = False
    faultyPacketIgnored = False

    ser.flushInput()
    ser.flushOutput()

    # Keep sending RESET packet and discard all bytes until the READY packet arrives
    while lastSeqNr == -1:
        print('Connecting to OpenMote...')
        ser.write(encode('RST' + chr(channel)))
        begin = time.time()
        while time.time() - begin < 1:
            c = ser.read(1)
            if len(c) > 0:
                c = bytearray(c)[0]
                if not receiving:
                    if c == HDLC_FLAG:
                        receiving = True
                        word = ''
                else:
                    if c == HDLC_FLAG:
                        if len(word) != 0:
                            receiving = False
                            word = decode(word, quiet=True)[0]
                            if len(word) > 0:
                                if word == 'READY':
                                    lastSeqNr = 0
                                    expectedSeqNr = 1
                                    break
                    else:
                        word += chr(c)

    print('Connected to OpenMote')

    while(True):
        c = ser.read(1)
        if len(c) > 0:
            c = bytearray(c)[0]
            if not receiving:
                if c == HDLC_FLAG:
                    receiving = True
                    word = ''
                else:
                    print('WARNING: byte dropped')
            else:
                if c == HDLC_FLAG:
                    if len(word) == 0:
                        print('WARNING: out of sync detected')
                    else:
                        # Get the timestamp
                        ts_sec = int(time.time())
                        ts_usec = int((time.time() - ts_sec) * 1000000)

                        receiving = False
                        word = decode(word)[0]
                        if len(word) > 0:
                            if word == 'READY':
                                print('Sniffer reset detected, restarting')
                                return True

                            # Ignore the packet if it had a wrong sequence number
                            if expectedSeqNr == (ord(word[2]) << 8) + ord(word[3]):
                                expectedSeqNr += 1
                                if expectedSeqNr == 65536:
                                    expectedSeqNr = 1
                                """
                                totalCount += 1
                                count += 1
                                if count == 60000:
                                    count = 1

                                receivedCount = (ord(word[4]) << 8) + ord(word[5])
                                print(str(totalCount) + ' ' + str(count) + ' ' + str(receivedCount) + ' ' + str(len(word)-6) + ' ' + str((ord(word[0]) << 8) + ord(word[1])) + ' ' + str((ord(word[2]) << 8) + ord(word[3])) + ' ' + str(ord(word[-2])) + ' ' + str(ord(word[-1])))
                                # Ignore the count in the packet when the CRC was wrong
                                if ord(word[-1]) & 128 == 0:
                                    print("WARNING: invalid radio CRC in packet " + str(totalCount))
                                elif count != receivedCount:
                                    print("ERROR: Packet lost!")
                                    return False
                                """

                                # Remember the index and sequence number of this packet in case the next one is corrupted
                                lastIndex = (ord(word[0]) << 8) + ord(word[1])
                                lastSeqNr = (ord(word[2]) << 8) + ord(word[3])

                                # Convert the string to a bytearray to write it to the pipe
                                packet = bytearray()
                                for character in word[4:]:
                                    packet.append(ord(character))

                                # TODO: Does LQI value has to be adapted?

                                # Write Record Header to pipe
                                header = bytearray()
                                header.append((ts_sec >> 24) & 0xff) # timestamp seconds
                                header.append((ts_sec >> 16) & 0xff) # timestamp seconds
                                header.append((ts_sec >> 8) & 0xff)  # timestamp seconds
                                header.append((ts_sec >> 0) & 0xff)  # timestamp seconds
                                header.append((ts_usec >> 24) & 0xff) # timestamp microseconds
                                header.append((ts_usec >> 16) & 0xff) # timestamp microseconds
                                header.append((ts_usec >> 8) & 0xff)  # timestamp microseconds
                                header.append((ts_usec >> 0) & 0xff)  # timestamp microseconds
                                header.extend([0, 0, len(packet) >> 8, len(packet) & 0xff]) # nr of octets of packet saved
                                header.extend([0, 0, len(packet) >> 8, len(packet) & 0xff]) # actual length of packet
                                pipe.write(header)

                                # Write the packet to the pipe
                                pipe.write(packet)
                            else:
                                print('WARNING: Received packet with seqNr=' + str((ord(word[2]) << 8) + ord(word[3]))
                                      + ' while expecting packet with seqNr=' + str(expectedSeqNr))

                            # Send an ACK after enough bytes have been received
                            unackedByteCount += len(word)
                            if unackedByteCount >= 250 and lastSeqNr != 0:
                                unackedByteCount = 0
                                ser.write(encode('ACK' + chr((lastIndex >> 8) & 0xff) + chr(lastIndex & 0xff)
                                                       + chr((lastSeqNr >> 8) & 0xff) + chr(lastSeqNr & 0xff)))
                        else:
                            print('NACK ' + str((lastIndex >> 8) & 0xff) + ' ' + str(lastIndex & 0xff) + ' '
                                          + str((lastSeqNr >> 8) & 0xff) + ' ' + str(lastSeqNr & 0xff))
                            ser.write(encode('NACK' + chr((lastIndex >> 8) & 0xff) + chr(lastIndex & 0xff)
                                                    + chr((lastSeqNr >> 8) & 0xff) + chr(lastSeqNr & 0xff)))
                else: # Not the closing byte
                    word += chr(c)

        else: # No character was read
            if receiving:
                receiving = False
                print('WARNING: expected another byte, assuming out of sync')
                print('NACK ' + str((lastIndex >> 8) & 0xff) + ' ' + str(lastIndex & 0xff) + ' '
                              + str((lastSeqNr >> 8) & 0xff) + ' ' + str(lastSeqNr & 0xff))
                ser.write(encode('NACK' + chr((lastIndex >> 8) & 0xff) + chr(lastIndex & 0xff)
                                        + chr((lastSeqNr >> 8) & 0xff) + chr(lastSeqNr & 0xff)))

    # The program has ended and does not require a restart
    return False

def main():
    # TODO Possible parameters
    # -c    Channel to start listening on.
    #       By default the sniffer will ask you to type the channel when starting.
    # -s    Full name of serial port to use. On linux this is e.g. "/dev/ttyUSB0".
    #       When not provided and multiple ports are available, sniffer will make you pick a port from a list.
    # -x    Wireshark executable.
    #       By default the sniffer will try to execute "wireshark" and ask for the correct name if it fails.
    # -p    Name of the fifo pipe to create.
    #       By default the pipe file is called "fifopipe".

    channel = None
    serialPortName = None
    wiresharkExe = 'wireshark-gtk'
    pipeName = 'fifopipe'

    global ser
    global pipe

    if serialPortName == None:
        selectedPort = pickSerialPort()
        if selectedPort == None:
            return

    ser = serial.Serial(port     = selectedPort,
                        baudrate = 460800, # 2000000, # 921600, # 460800, # 115200
                        parity   = serial.PARITY_NONE,
                        stopbits = serial.STOPBITS_ONE,
                        bytesize = serial.EIGHTBITS,
                        xonxoff  = False,
                        rtscts   = False,
                        dsrdtr   = False,
                        timeout   = 0.25)

    createPipe(pipeName)

    if channel == None:
        channel = pickRadioChannel()
        if channel == None:
            removePipe(pipeName)
            quit()

    # TODO: Start wireshark here but then start a different script with root access that connects to the sniffer
    #       Example code below restarts current script, sys.argv should of course be edited in our version
    #args = ['sudo', sys.executable] + sys.argv + [os.environ]
    #os.execlpe('sudo', *args)

    # Start wireshark and wait until it is listening to our pipe
    print('Starting wireshark...')
    subprocess.Popen([wiresharkExe, '-k', '-i', pipeName])
    print('Waiting for wireshark to be ready...')
    pipe = open(pipeName, 'wb', buffering=0)
    print('Connected to wireshark')

    # Write the global header to the pipe
    header = bytearray()
    header.extend([0xa1, 0xb2, 0xc3, 0xd4])  # magic number
    header.extend([0, 2]) # major version number
    header.extend([0, 4]) # minor version number
    header.extend([0]*4)  # GMT to local correction
    header.extend([0]*4)  # accuracy of timestamps
    header.extend([0, 0, 0xff, 0xff])  # max length of captured packets, in octets
    header.extend([0, 0, 0, 195])  # 802.15.4 protocol
    pipe.write(header)

    try:
        while True:
            try:
                program(channel)
            except (KeyboardInterrupt):
                pass
            ser.write(encode('STOP'))

            channel = pickRadioChannel()
            if channel == None:
                break
    except (KeyboardInterrupt):
        pass

    pipe.close()
    removePipe(pipeName)


if __name__ == "__main__":
    main()
