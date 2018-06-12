#!/usr/bin/python3

from __future__ import print_function
from queue import *
from threading import Thread
from tempfile import mkstemp
#import tempfile
import time
import sys
import frida
import binascii
import argparse
import webbrowser
import subprocess
import os

block = True

def do_stuff(queueFridaBuffers, queueUserInput):
    while True:
        print(queueFridaBuffers.get())
        queueFridaBuffers.task_done()

        print(queueUserInput.get())
        queueUserInput.task_done()

def run_frida_stuff(queueFridaBuffers, queueUserInput):
    #print("[*] Starting run_frida_stuff")
    #fakeBuffers = ["\x65\x65\x65\x00", "\x66\x66\x66\x00", "\x67\x67\x67\x00", "\x68\x68\x68\x00"]
    #for buff in fakeBuffers:
    buff = "\x65\x65\x00"
    hasPrintedBuffer = False
    #    queueFridaBuffers.put(buff)
        #print("[*] In frida loop")
    if queueUserInput.empty() and not hasPrintedBuffer:
        print(buff)
    while queueUserInput.empty():
        #print(queueFridaBuffers.get())
        #print("[FRIDA] No User Input")
        pass
    else:
        userInput = queueUserInput.get()
        print("[FRIDA] User input is:" + userInput)
        if(userInput == "y"):
            queueFridaBuffers.get()
    #sys.stdin.read()

def attach(queueFridaBuffers, queueUserInput, processToAttach):
    print("[*] Attaching to " + str(processToAttach))
    session = frida.attach(processToAttach)

    script = session.create_script("""
    functionPointer = Module.findExportByName(null, "SSL_write");
    Interceptor.attach(ptr(functionPointer), {
        onEnter: function(args) {
            var buf = Memory.readByteArray(ptr(args[1]), args[2].toInt32());
            var ruleAndLength = "Client --> Server, " + args[2].toInt32().toString() + " byte message.";
            send(ruleAndLength, buf);
            var userResponse = recv('input', function(value) {
                args[0] = ptr(value.payload);
            });
            userResponse.wait();
        }
    });
    """)
    script.on('message', on_message)
    script.load()
    while block:
        time.sleep(1)

    exit(0)

def on_message(message, data):
    #print(message['payload'])
    if data:
        print(message['payload'])
        print_bytes_for_ui(data)
        queueFridaBuffers.put(data)
        #willEdit = "wait"
        #while(willEdit == "wait"):
        #    pass
        queueUserInput.get()
        print("[FridaThread] Passed queue wait")
        return 0
    else:
        print(message)

def write_file(message):
    fileMode = 'a+'
    if isinstance(message, str):
        fileMode = 'a+'
    elif isinstance(message, bytes):
        fileMode = 'ab+'
    with open('../testfile', fileMode) as f:
        read_data = f.read()
        print("[*] reading from testfile")
        print(read_data)
        f.write(message)
        f.close()
    with open('../testfile', 'a') as f:
        f.write('\n')
        f.close()
    return 0

#def string_to_bytes(stringToBytes):
#    newBytes = codecs.decode(stringToBytes, 'unicode_escape')
#    return(newBytes)

def select_os(osSelection):
    if(osSelection == "determine"):
        osSelection = sys.platform
    elif(osSelection == "linux"):
        osSelection = "linux"
    elif(osSelection == "mac"):
        osSelection = "darwin"
    elif(osSelection == "windows"):
        osSelection = "win32"
    else:
        osSelection = "linux"

    return(osSelection)

def user_input_thread(queueFridaBuffers, queueUserInput):
    print("[*] Starting user_input_thread")
    while True:
        print("[*] In user input loop")
        if queueUserInput.empty():
            willEdit = will_user_edit()
            queueUserInput.put(willEdit)
        #time.sleep(2)
        pass

def print_bytes_for_ui(inBytes, length=16):
    print("          0  1  2  3  4  5  6  7  8  9  A  B  C  D  E  F 0123456789ABCDEF")
    lines = bytes_to_human_lines(inBytes, length)
    for j in range(len(lines)):
        byte_index = j * 16
        readable = ''
        for c in lines[j]:
            byte = int(c, 16)
            if byte < 128:
                readable += chr(byte)
            else:
                readable += '.'
        output = hex(byte_index)[2:].zfill(8) + ' ' + ' '.join(lines[j])
        output += ' ' * (56 - len(output))
        print(output, readable)

def bytes_to_human_lines(inBytes, length=16):
    byteString = bytes_to_string(inBytes)
    return [byteString[x:x+length] for x in range(0, len(byteString), length)]

def bytes_to_string(inBytes):
    resp = []
    for x in inBytes:
        out = hex(x)[2:]
        if x < 10:
            out = '0' + out
        resp.append(out)
    return resp

def will_user_edit():
    print("[*] Starting will_user_edit")
    print("Edit Packet? Y/n")
    userInput = input()
    if(userInput.lower() == "n" or userInput.lower() == "no"):
        userInput = "n"
        #print("Did not choose to edit")
    else:
        userInput = "y"
        #print("Chose to edit")
    return(userInput)

queueFridaBuffers = Queue(maxsize=0)
queueUserInput = Queue(maxsize=0)
num_threads = 2

def make_bytes_for_temp_file(inBytes, length=16):
    output = ''
    blockOfHexBytes = ''
    instructions = '[*] Edit hex below. Save and quit to make changes.\n'
    readable = ''
    readableSizePerLine = 0
    lines = bytes_to_human_lines(inBytes, length)
    for j in range(len(lines)):
        for c in lines[j]:
            byte = int(c, 16)
            if byte < 128:
                readable += chr(byte)
            else:
                readable += '.'
            if readableSizePerLine >= length - 1:
                readable += '\n'
                readableSizePerLine = 0
            else:
                readableSizePerLine+=1
        blockOfHexBytes += ' '.join(lines[j])
        blockOfHexBytes += '\n'
    appendOldBytes = "[*] End of hex\n[*] Original bytes were:\n" + blockOfHexBytes
    output += instructions + blockOfHexBytes + appendOldBytes + "[*] ASCII was:\n" + readable
    return(output)

def edit_bytes_in_temp_file(byteString):
    newByteString = byteString
    #with tempfile.TemporaryFile('w+') as tmp:
    #    tmp.write(byteString)

    try:
        editor = os.getenv("EDITOR")
        if editor:
            print(editor)
        else:
            editor = 'vi'
    finally:
        print("Passed Try")

    tempFileDescriptor, tempFilePath = mkstemp(text=True)
    try:
        with os.fdopen(tempFileDescriptor, 'w') as tmp:
            #print("byteString:\n"+byteString)
            tmp.write(byteString)
            #tmp.write(byteString)
            tmp.flush()
            os.fsync(tmp.fileno())
            editProc = subprocess.Popen(['vim', '-f', '-o'], close_fds=True, stdout=None)
            editProc.communicate()
            input("Test:"+tempFilePath)
    finally:
        os.remove(tempFilePath)

    '''
    tmp = tempfile.NamedTemporaryFile("w+", delete=True)
    try:
        print("byteString:\n"+byteString)
        tmp.write(byteString)
        tmp.flush()
        os.fsync(tmp.fileno())
        print(tmp.name())
        #webbrowser.open_new_tab()
        input("Test")
    finally:
        tmp.close()
    '''

    #print(tempFileDescriptor)
    #print(type(tempFilePath))

        #print(tmp.read())
    #f.write(byteString)
    #file = open("testfile","w+")
    #file.write(byteString)
    return(newByteString)

def read_byte_string(byteString):
    hex_list = byteString.split()
    return bytes([int(x, 16) for x in hex_list])

def main():
    print("[*] Starting MAIN")

    # Default to Linux OS
    os = 'linux'
    hasUserGivenInput = False
    parser = argparse.ArgumentParser()
    #parser.add_argument('help', metavar='h', type=str, help='The help flag')
    parser.add_argument("-o", "--os", help="Set OS to either 'linux', 'windows', or 'mac'", type=str, choices=["linux", "windows", "mac"])
    connectToProcessGroup = parser.add_mutually_exclusive_group()
    connectToProcessGroup.add_argument("-p", "--pid", help="pid to attach to", type=int)
    connectToProcessGroup.add_argument("-n", "--name", help="process name to attach to", type=str)

    args = parser.parse_args()

    # Select OS
    if(args.os):
        os = select_os(args.os)
    else:
        os = select_os("determine")

    if(args.pid):
        fridaThread = Thread(target=attach, args=(queueFridaBuffers, queueUserInput, args.pid))
    elif(args.name):
        fridaThread = Thread(target=attach, args=(queueFridaBuffers, queueUserInput, args.name))
    else:
        exit("Please provide either a PID (-p) or process name (-n)")

    fridaThread.setDaemon(True)
    fridaThread.start()

    while True:
        if not queueFridaBuffers.empty():
            fridaBuffer = queueFridaBuffers.get()
            willEdit = will_user_edit()
            if(willEdit == "y"):
                bytesToEdit = make_bytes_for_temp_file(fridaBuffer)
                edit_bytes_in_temp_file(bytesToEdit)
            print(willEdit)
            queueUserInput.put(willEdit)
        else:
            pass

    exit(0)

if __name__ == "__main__":
    main()
    exit('How did you reach this branch?')