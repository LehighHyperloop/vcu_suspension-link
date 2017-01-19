import socket
import sys
import struct
import errno
import random
import time
import logging


port=3000
ip='192.168.0.151'
now = time.strftime('%Y_%m_%d %H-%M-%S')

print("\n\n\nVCU STUB IMPLEMENTATION by E-Shock s.r.l.\n\n\n")
print("Connecting to \"%s\"" % ip)

# Create a UDP socket
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_sock.bind(('', port))
server_address = (ip, port)
udp_sock.settimeout(0.01) #10 ms
#need to have a timeout because it changes socket from the default (blocking) mode

# Create a TCP socket
tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_sock.connect((ip, port))
# tcp_sock.settimeout(0.01) #10 ms



network_endianness = ''

print >>sys.stderr, 'System endianness: ' + sys.byteorder

if sys.byteorder == 'little':
    network_endianness='>'
    print >>sys.stderr, 'Network endianness: opposite of system\'s'
else:
    network_endianness='<'
    print >>sys.stderr, 'Network endianness: same as system\'s'


my_speed_const = 123.456
my_acceleration_const = 789.543
my_speed = 123.456
my_acceleration = 789.543
random_val = 10

speed_and_acceleration_periodic_message = struct.pack(network_endianness+'BBff', 0x20, 8, my_speed, my_acceleration);
ping_message_req = struct.pack(network_endianness+'BB', 0x10, 0);
start_scu_message_req = struct.pack(network_endianness+'BB', 0x11, 0);
start_logging_message_req = struct.pack(network_endianness+'BB', 0x12, 0);
stop_logging_message_req = struct.pack(network_endianness+'BB', 0x13, 0);
stop_scu_message_req = struct.pack(network_endianness+'BB', 0x14, 0);
available_space_message_req = struct.pack(network_endianness+'BB', 0x15, 0);
clear_logs_message_req = struct.pack(network_endianness+'BB', 0x16, 0);
heartbeat_message_reply = struct.pack(network_endianness+'BBH', 0x57, 2, 123);
clear_faults_message_req = struct.pack(network_endianness+'BB', 0x18, 0);

vcu_message_reply = ()
scu_message_request = ()
vcu_tcp_received_message = ()
vcu_udp_received_message = ()

try:
    while True:
        # Acquire input from the user
        try:
            key = raw_input("Enter a command: ") #used to be kbfunc, made it like a terminal instead
                                                 #will eventually run like a daemon

            if (key == "p"):
                print('PING REQUEST %s' % [hex(ord(c)) for c in ping_message_req])
                tcp_sock.send(ping_message_req)
            elif (key == "s"):
                print('START SCU REQUEST %s' % [hex(ord(c)) for c in start_scu_message_req])
                tcp_sock.send(start_scu_message_req)
            elif (key == "d"):
                print('STOP SCU REQUEST %s' % [hex(ord(c)) for c in start_scu_message_req])
                tcp_sock.send(stop_scu_message_req)
            elif (key == "l"):
                print('START LOGGING REQUEST %s' % [hex(ord(c)) for c in start_logging_message_req])
                tcp_sock.send(start_logging_message_req)
            elif (key == "k"):
                print('STOP LOGGING REQUEST %s' % [hex(ord(c)) for c in stop_logging_message_req])
                tcp_sock.send(stop_logging_message_req)
            elif (key == "a"):
                print('AVAILABLE SPACE REQUEST %s' % [hex(ord(c)) for c in available_space_message_req])
                tcp_sock.send(available_space_message_req)
            elif (key == "c"):
                print('CLEAR FAULTS REQUEST %s' % [hex(ord(c)) for c in clear_logs_message_req])
                sent = tcp_sock.send(clear_logs_message_req)
            elif (key == "r"):
                print('CLEAR LOGS REQUEST %s' % [hex(ord(c)) for c in clear_faults_message_req])
                sent = tcp_sock.send(clear_faults_message_req)
            elif (key == "x"):
                print >>sys.stderr, 'exiting....'
                break
            else:
                print "Unknown command"
                continue

            # TCP receive
            vcu_tcp_received_message = tcp_sock.recv(1024)
            scu_message_request =  struct.unpack_from(network_endianness+'BB', vcu_tcp_received_message)

            # Handling of received packet
            if (scu_message_request[0] == 0x17): #HEARTBEAT REQUEST
                scu_message_request =  struct.unpack_from(network_endianness+'BB', vcu_tcp_received_message)
                tcp_sock.send(heartbeat_message_reply)
                print('* (Heartbeat)')
            elif (scu_message_request[0] == 0x50): # PING REPLY
                scu_message_request =  struct.unpack_from(network_endianness+'BBH', vcu_tcp_received_message)
                print('PING REPLY - FW vers: %d' % scu_message_request[2:])
            elif (scu_message_request[0] == 0x51): # START SCU REPLY
                scu_message_request =  struct.unpack_from(network_endianness+'BBH', vcu_tcp_received_message)
                print('START SCU REPLY - Start Fault %d' % scu_message_request[2:])
            elif (scu_message_request[0] == 0x54): # STOP SCU REPLY
                scu_message_request =  struct.unpack_from(network_endianness+'BBH', vcu_tcp_received_message)
                print('STOP SCU REPLY - Stop Fault %d' % scu_message_request[2:])
            elif (scu_message_request[0] == 0x52): # START LOGGING REPLY
                scu_message_request =  struct.unpack_from(network_endianness+'BB14s', vcu_tcp_received_message)
                print('START LOGGING REPLY - Filename %s' % scu_message_request[2:])
            elif (scu_message_request[0] == 0x53): # STOP LOGGING REPLY
                scu_message_request =  struct.unpack_from(network_endianness+'BB14s', vcu_tcp_received_message)
                print('STOP LOGGING REPLY - Filename %s' % scu_message_request[2:])
            elif (scu_message_request[0] == 0x56): # CLEAR LOGS
                scu_message_request =  struct.unpack_from(network_endianness+'BBfH', vcu_tcp_received_message)
                print('CLEAR LOGS REPLY - Available space %d Clear log faults %d' % scu_message_request[2:])
            elif (scu_message_request[0] == 0x55): # AVAILABLE SD SPACE
                scu_message_request =  struct.unpack_from(network_endianness+'BBf', vcu_tcp_received_message)
                print('AVAILABLE SD SPACE REPLY - Available space %d MB' % scu_message_request[2:])
            elif (scu_message_request[0] == 0x58): # CLEAR FAULTS
                scu_message_request =  struct.unpack_from(network_endianness+'BBH', vcu_tcp_received_message)
                print('CLEAR FAULT REPLY - Clear faults fault %d' % scu_message_request[2:])
            else:
                print('TCP received "%s"' % [hex(ord(c)) for c in vcu_tcp_received_message])
                print( 'TCP received length of TCP datagram "%s"' % len(scu_message_request))

        except socket.timeout, e:
            print "Failed to connect to socket:", e
            continue

        print

        # Send UDP data
        my_speed = my_speed_const+random.random()*random_val
        my_acceleration = my_acceleration_const+random.random()*random_val
        speed_and_acceleration_periodic_message = struct.pack(network_endianness+'BBff', 0x20, 8, my_speed, my_acceleration);
        dic_message = 0 #to make it run, no idea wtf this is supposed to be
        sent = udp_sock.sendto(speed_and_acceleration_periodic_message, dic_message, server_address)

        try:
            msg = udp_sock.recv(4096)
        except socket.timeout, e:
            err = e.args[0]
            # this next if/else is a bit redundant, but illustrates how the
            # timeout exception is setup
            if err == 'timed out':
                continue
            else:
                print e
                sys.exit(1)
        except socket.error, e:
            # Something else happened, handle error, exit, etc.
            print e
            sys.exit(1)
        else: #if there is no error
            if len(msg) != 0:
                vcu_udp_received_message =  struct.unpack_from(network_endianness+'BB', msg)

                # Handling UDP received package

                if (vcu_udp_received_message[0] == 0x21):
                    vcu_udp_received_message =  struct.unpack_from(network_endianness+'BBfffffffHH', msg)
                    print('SUSPENSION TRAVELS FL: %f FR: %f RL: %f RR: %f X Acc: %f Y Acc:  %f Z Acc:  %f Faults:  %d Status: %d' % vcu_udp_received_message[2:])
                elif (vcu_udp_received_message[0] == 0x22):
                    vcu_udp_received_message =  struct.unpack_from(network_endianness+'BBffff', msg)
                    print('PAD DISTANCES FL: %f FR Pad: %f RL: %f RR Pad: %f' % vcu_udp_received_message[2:])
                else:
                    print('TCP received "%s"' % [hex(ord(c)) for c in vcu_udp_received_message])


finally:
   print >>sys.stderr, 'closing socket'
   udp_sock.close()
