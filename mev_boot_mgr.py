#!/usr/bin/env python3

import os
import sys
import serial
import time
import subprocess

filt = False
fkey = 'invalid fkey'
pref = True
rot =['|', '/', '-', '\\']

def wait_for_xhc(hostname):
    global filt
    global rot
    i = 0
    while True:
        idx = i & 0x3
        i = i + 1
        if filt == False:
            print('  Waiting for {} to come up {}'.format(hostname,
                rot[idx]), end='\r')
        if idx == 0:
            stat = os.system('ping -c 1 {} > /dev/null 2>&1'.format(hostname))
            if stat == 0:
                if filt == False:
                    print('\nServer {} is alive!'.format(hostname))
                break
        else:
            time.sleep(1)


def open_ssh(hostname):
    global filt
    global rot
    i = 0
    while True:
        idx = i & 0x3
        i = i + 1
        if filt == False:
            print('  Waiting for SSH to {} to come up {}'.format(hostname,
                rot[idx]), end='\r')
        ssh_dev = subprocess.Popen(['ssh', hostname],
                                    stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True,
                                    bufsize=0)
        time.sleep(1)
        ssh_dev.poll()
        if ssh_dev.returncode == None:
            if filt == False:
                print('\nSSH to {} is alive!'.format(hostname))
            break

    return ssh_dev


def send_ssh_command(ssh_dev, dev_name, command):
    global filt

    try:
        if filt == False:
            if pref == True:
                print('{}: {}'.format(dev_name, command))
            else:
                print(command)
        ssh_dev.stdin.write('{}\n'.format(command))
        ssh_dev.stdin.write('echo END\n')
        for line in ssh_dev.stdout:
            if line.startswith('END'):
                break
            if filt == False:
                if pref == True:
                    print('{}: {}'.format(dev_name,line), end='')
                else:
                    print(line, end='')
    except BrokenPipeError:
        pass


def wait_for_con_line(con_dev, wait_line, devname):
    global rot
    i = 0
    buf = bytearray('', 'latin-1')
    while True:
        idx = i & 0x3
        i = i + 1
        c = con_dev.read()
        if c == b'\r':
            continue
        if c == b'\n':
            str = buf.decode('latin-1')
            if filt == False or str.startswith(fkey):
                if fkey in str:
                        str = str.split(fkey)[1].strip()
                if pref == True:
                    print('{}: {}'.format(devname, str))
                else:
                    print(str)
            buf = bytearray('', 'latin-1')
        else:
            buf = buf + c

        if wait_line in buf.decode('latin-1'):
            str = buf.decode('latin-1')
            if filt == False or fkey in str:
                if str.startswith(fkey):
                        str = str.split(fkey)[1].strip()
                if pref == True:
                    print('{}: {}'.format(devname, str))
                else:
                    print(str)
            time.sleep(2)
            return
        print(' {}'.format(rot[idx]), end='\r')


def send_con_command(con_dev, devname, command):
    global filt
    global pref
    global fkey
    login = 0

    if command == 'LOGIN':
        command = 'TYPE-1 root'
        login = 0
    elif command == 'LOGOUT':
        command = 'TYPE-1 logout'

    if command.startswith('WAIT_FOR '):
        if filt == False:
            if pref == True:
                print('{0}: {1}'.format(devname, command))
            else:
                print(command)
        wait_line = command.split('WAIT_FOR ')[1]
        wait_for_con_line(con_dev, wait_line, devname)
    elif command.startswith('TYPE-'):
        if filt == False:
            if pref == True:
                print('{0}: {1}'.format(devname, command))
            else:
                print(command)
        tmo = float(command.strip('TYPE-').split(' ')[0])
        cmd = command.split(' ', 1)[1]
        con_dev.write('{}\r\n'.format(cmd).encode('latin-1'))
        start_time = time.time()
        while time.time() - start_time < tmo:
            data = con_dev.readline().decode('latin-1').replace("\r\n","")
            if data and filt == False:
                if pref == True:
                    print('{0}: {1}'.format(devname, data))
                else:
                    print(data)
    else:
        con_dev.write('{}\r\n'.format(command).encode('latin-1'))
        con_dev.write('echo END\r\n'.encode('latin-1'))
        while True:
            data = con_dev.readline().decode('latin-1').replace("\r\n","")
            if data:
                if data.startswith('END'):
                    break
                if data.startswith('echo END'):
                    continue
                if data.startswith('root@mev-imc:'):
                    continue
                if filt == False or data.startswith(fkey):
                    if data.startswith(fkey):
                        data = data.split(fkey)[1].strip()
                    if pref == True:
                        print('{0}: {1}'.format(devname, data))
                    else:
                        print(data)
    if login == 1:
        date_s = os.popen('date -u').read()
        send_con_command(con_dev, devname, 'date -s \"' + date_s + '\"')

def exit_ssh_dev(ssh_dev):
    try:
        ssh_dev.stdin.write("logout\n")
        ssh_dev.stdin.flush()
        ssh_dev.stdout.flush()
        ssh_dev.stderr.flush()
        ssh_dev.stdin.close()
        ssh_dev.stdout.close()
        ssh_dev.stderr.close()
    except BrokenPipeError:
        pass

def exit_con_dev(con_dev):
        con_dev.flush()
        con_dev.close()

def main():
    dev_names =   ['XHC-SSH', 'IMC-SSH', 'ACC-SSH', 'NUC-SSH', 'IMC-CON', 'ACC-CON']
    dev_addr =    ['','','','','','']
    dev_active =  [False, False, False, False, False, False]
    dev_handler = [None, None, None, None, None, None]
    dev_is_ssh =  [True, True, True, True, False, False]
    dev_sub_ssh = [False, True, True, False, False, False]
    dev_baud =    [0, 0, 0, 0, 460800, 115200]

    dev_idx = -1
    com_mode = 0
    filename = ''

    global pref
    global filt
    global fkey

    if len(sys.argv) > 1:
        filename=sys.argv[1]
    file = open(filename, 'r')
    lines = file.readlines()
    file.close()
    for line in lines:
        line = line.strip()
        if line.startswith('#{'):
            com_mode = com_mode + 1
            continue
        elif line.startswith('#}') and com_mode > 0:
            com_mode = com_mode - 1
            continue
        elif line.startswith('#') or len(line) == 0 or com_mode > 0:
            continue
        elif line.startswith('ECHO '):
            if dev_idx == -1 or pref == False:
                print(line.split('ECHO ')[1])
            else:
                print('{}: {}'.format(dev_names[dev_idx], line.split('ECHO ')[1]))
            continue
        elif line.startswith('FILT '):
            arg_line = line.split('FILT ')[1]
            if arg_line.startswith('ON'):
                filt = True
            elif arg_line.startswith('OFF'):
                filt = False
            continue
        elif line.startswith('PREF '):
            arg_line = line.split('PREF ')[1]
            if arg_line.startswith('ON'):
                pref = True
            elif arg_line.startswith('OFF'):
                pref = False
            continue
        elif line.startswith('FKEY '):
            fkey = line.split('FKEY ')[1]
            continue

        match = False
        for idx, name in enumerate(dev_names):
            if line == '{}:'.format(name):
                dev_idx = idx
                match = True
                if dev_active[idx] == False:
                    if dev_is_ssh[idx] == True:
                        wait_for_xhc(dev_addr[idx])
                        dev_handler[idx] = open_ssh(dev_addr[idx])
                        if dev_sub_ssh[idx]:
                            send_ssh_command(dev_handler[idx], name,
                                'ssh root@{}'.format(dev_addr[idx]))
                    else:
                        dev_handler[idx] = serial.Serial(dev_addr[idx],
                                                    dev_baud[idx], timeout=1.0)
                    dev_active[idx] = True
                break
        if match == True:
            continue

        if dev_idx == -1:
            bad_line = True
            for idx, name in enumerate(dev_names):
                if line.startswith('{}='.format(name)):
                    dev_addr[idx] = line.split('=', 1)[1]
                    bad_line = False
                    break
            if bad_line:
                print('Invalid config line: {}'.format(line))
                return -1
            continue
        else:
            if dev_is_ssh[dev_idx]:
                send_ssh_command(dev_handler[dev_idx], dev_names[dev_idx], line)
                if line.startswith('reboot'):
                    exit_ssh_dev(dev_handler[dev_idx])
                    time.sleep(20)
                    wait_for_xhc(dev_addr[dev_idx])
                    dev_handler[dev_idx] = open_ssh(dev_addr[dev_idx])
            else:
                send_con_command(dev_handler[dev_idx], dev_names[dev_idx], line)

    for idx, active in enumerate(dev_active):
        if dev_active[idx] == True:
            if dev_is_ssh[idx]:
                if dev_sub_ssh[idx]:
                    try:
                        dev_handler[idx].stdin.write("logout\n")
                    except BrokenPipeError:
                        pass
                exit_ssh_dev(dev_handler[idx])
            else:
                exit_con_dev(dev_handler[idx])

    return 0

# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
if __name__ == '__main__':
    main()
