import json
import os
import paho.mqtt.client as mqtt
import socket
import time
import struct
import sys

SUBSYSTEM = "remote_subsystem/suspension"
MQTT_IP = "192.168.0.100"
SUSPENSION_IP = "192.168.0.151"
SUSPENSION_PORT = 3000

network_endianness = ''

def get_endianness():
    if sys.byteorder == "little":
        network_endianness=">"
        print >>sys.stderr, "Network endianness: opposite of system\'s"
    else:
        network_endianness="<"
        print >>sys.stderr, "Network endianness: same as system\'s'"

# SPEED_AND_ACCELERATION_PERIODIC_MESSAGE = struct.pack(network_endianness+'BBff', 0x20, 8, my_speed, my_acceleration);
# have to build this ^ one when you have the speed and acceleration
# not sure how often you actually have to send it though since it's "periodic"
PING_MESSAGE_REQ = struct.pack(network_endianness+"BB", 0x10, 0);
START_SCU_MESSAGE_REQ = struct.pack(network_endianness+"BB", 0x11, 0);
START_LOGGING_MESSAGE_REQ = struct.pack(network_endianness+"BB", 0x12, 0);
STOP_LOGGING_MESSAGE_REQ = struct.pack(network_endianness+"BB", 0x13, 0);
STOP_SCU_MESSAGE_REQ = struct.pack(network_endianness+"BB", 0x14, 0);
AVAILABLE_SPACE_MESSAGE_REQ = struct.pack(network_endianness+"BB", 0x15, 0);
CLEAR_LOGS_MESSAGE_REQ = struct.pack(network_endianness+"BB", 0x16, 0);
HEARTBEAT_MESSAGE_REPLY = struct.pack(network_endianness+"BBH", 0x57, 2, 123);
CLEAR_FAULTS_MESSAGE_REQ = struct.pack(network_endianness+"BB", 0x18, 0);

# External and internal states
_state = {
    "state": "IDLE",
    "t_state": "IDLE"
}

#map of the actual message to send over TCP for
#each of the abstract messages like "start SCU"
_message_to_bytestring = {
    "START_SCU": START_SCU_MESSAGE_REQ,
    "STOP_SCU": STOP_SCU_MESSAGE_REQ,
    "START_SCU_LOGGING": START_LOGGING_MESSAGE_REQ,
    "STOP_SCU_LOGGING": STOP_LOGGING_MESSAGE_REQ,
    "CLEAR_FAULT": CLEAR_FAULTS_MESSAGE_REQ,
    "CLEAR_LOGS": CLEAR_LOGS_MESSAGE_REQ,
    "AVAILABLE_SPACE": AVAILABLE_SPACE_MESSAGE_REQ,
    "PING": PING_MESSAGE_REQ, #send to SCU to see if it's alive
    "HEARTBEAT_REPLY": HEARTBEAT_MESSAGE_REPLY #response if SCU asks if we're alive
}

#convert the status code the SCU gives us into one of our actual
#states. Might be able to just change the order around in the
#other dict to match the order of the states and index it like an array?
_status_code_to_state = {
    1 : "INIT",
    2 : "HOMING",
    3 : "READY",
    4 : "RUNNING",
    5 : "FAULT"
}

def idle_func(t, tcp_sock):
    if t == "READY":
        signal("START_SCU", tcp_sock)

def homing_func(t, tcp_sock):
    pass
    # since transition is automatic from homing to ready,
    # we can just wait until the SCU reports it is ready, which will be
    # handled by the transition() function

def ready_func(t, tcp_sock):
    if t == "RUNNING":
        signal("START_SCU", tcp_sock)

def running_func(t, tcp_sock):
    if t == "READY":
        signal("STOP_SCU", tcp_sock)
    elif t == "RUNNING_AND_LOGGING":
        signal("START_SCU_LOGGING", tcp_sock)

#note: can only start logging when already running
def running_and_logging_func(t, tcp_sock):
    if t == "READY":
        signal("STOP_SCU", tcp_sock)
    elif t == "RUNNING":
        signal("STOP_SCU_LOGGING", tcp_sock)

#actually need a fault transition in this one because
#their system will lock itself into FAULT state and
#not do anything until it receives "CLEAR FAULT"
def fault_func(t, tcp_sock):
    signal("CLEAR_FAULT", tcp_sock)
    signal("STOP_SCU", tcp_sock) #default transition is Fault->Running, this sets it back to running


#takes in a message from the list and actually sends the TCP communication,
#and waits for the response from the SCU
#might need to return True/False in the future idk
def signal(message, tcp_sock):
    if tcp_sock is None:
        print "No TCP connection [signal]"
        return

    if message not in _message_to_bytestring:
        print "Bad command [signal]"
        return

    #send appropriate bytestring for message
    tcp_sock.send(_message_to_bytestring[message])

    #hear what the SCU says back over TCP
    vcu_tcp_received_message = tcp_sock.recv(1024)
    scu_message_request =  struct.unpack_from(network_endianness+'BB', vcu_tcp_received_message)

    # Handling of received packet, each one has to be decoded differently
    # eventually instead of just printing this will have to actually handle the
    # different responses the SCU can give with control code...
    if (scu_message_request[0] == 0x17): # SCU requests heartbeat, send it
        scu_message_request =  struct.unpack_from(network_endianness+'BB', vcu_tcp_received_message)
        signal("HEARTBEAT_REPLY", tcp_sock)
        print "Responded to SCU heartbeat req"
    elif (scu_message_request[0] == 0x50): # SCU replied to our ping
        scu_message_request =  struct.unpack_from(network_endianness+'BBH', vcu_tcp_received_message)
        print('PING REPLY - FW vers: %d' % scu_message_request[2:])
    elif (scu_message_request[0] == 0x51): # SCU replied to our request to start
        scu_message_request =  struct.unpack_from(network_endianness+'BBH', vcu_tcp_received_message)
        print('START SCU REPLY - Start Fault %d' % scu_message_request[2:])
    elif (scu_message_request[0] == 0x54): # SCU replied to our request to stop
        scu_message_request =  struct.unpack_from(network_endianness+'BBH', vcu_tcp_received_message)
        print('STOP SCU REPLY - Stop Fault %d' % scu_message_request[2:])
    elif (scu_message_request[0] == 0x52): # SCU replied to our request to start logging
        scu_message_request =  struct.unpack_from(network_endianness+'BB14s', vcu_tcp_received_message)
        print('START LOGGING REPLY - Filename %s' % scu_message_request[2:])
    elif (scu_message_request[0] == 0x53): # SCU replied to our request to stop logging
        scu_message_request =  struct.unpack_from(network_endianness+'BB14s', vcu_tcp_received_message)
        print('STOP LOGGING REPLY - Filename %s' % scu_message_request[2:])
    elif (scu_message_request[0] == 0x56): # SCU replied to our request to clear logs
        scu_message_request =  struct.unpack_from(network_endianness+'BBfH', vcu_tcp_received_message)
        print('CLEAR LOGS REPLY - Available space %d Clear log faults %d' % scu_message_request[2:])
    elif (scu_message_request[0] == 0x55): # SCU replied with available space
        scu_message_request =  struct.unpack_from(network_endianness+'BBf', vcu_tcp_received_message)
        print('AVAILABLE SD SPACE REPLY - Available space %d MB' % scu_message_request[2:])
    elif (scu_message_request[0] == 0x58): # SCU replied to our request to clear logs
        scu_message_request =  struct.unpack_from(network_endianness+'BBH', vcu_tcp_received_message)
        print('CLEAR FAULT REPLY - Clear faults fault %d' % scu_message_request[2:])
    else: # SCU response does not match any of the ones it should be
        print "TCP received \"%s\"" % ([hex(ord(c)) for c in vcu_tcp_received_message])
        print "This is likely a malformed response from the SCU, or a code error"


#dispatches to functions to communicate over tcp_sock to change system state from current_state to t_state
def transition(current_state, t_state, tcp_sock):
    _possible_states[current_state](t_state, tcp_sock)
    if _state[current_state] != t_state: #currently keeps trying until state becomes what we want it to be
        transition(current_state, t_state, tcp_sock)

def set_state_from_scu(status):
    status = "get_the_state_number_from_the_string_idk_how_yet" #should just be an array index though
    new_state = _status_code_to_state[status] #this will have to decode the message from SCU into a state
    _state["state"] = new_state

#pull status from TCP and UDP and send it out
def logic_loop(client, tcp_sock, udp_sock):
    #
    #read in state from AlesTech system over streaming UDP connection
    #TCP is only in response to us, so we will look for a TCP response
    #only if we are told over mqtt to send a message to the system (see signal() function)
    #
    msg = ""
    try:
        msg = udp_sock.recv(4096)
    except socket.timeout, e: #if timeout, just keep waiting (logic_loop will be called again)
        return
    except socket.error, e: # an actual bad error
        print e
        sys.exit(1)
    else: #if there is no error, process message from system
        if len(msg) != 0:
            print "Got message over UDP:", msg
            vcu_udp_received_message =  struct.unpack_from(network_endianness+'BB', msg)

            #naturally prints will eventually be replaced with code for updating state or something
            #based on what the SCU says
            if (vcu_udp_received_message[0] == 0x21):
                vcu_udp_received_message =  struct.unpack_from(network_endianness+'BBfffffffHH', msg)
                print('SUSPENSION TRAVELS FL: %f FR: %f RL: %f RR: %f X Acc: %f Y Acc:  %f Z Acc:  %f Faults:  %d Status: %d' % vcu_udp_received_message[2:])
                set_state_from_scu(vcu_udp_received_message[2:])
            elif (vcu_udp_received_message[0] == 0x22):
                vcu_udp_received_message =  struct.unpack_from(network_endianness+'BBffff', msg)
                print('PAD DISTANCES FL: %f FR Pad: %f RL: %f RR Pad: %f' % vcu_udp_received_message[2:])
            else: #not sure why this says TCP instead of UDP but that's how theirs read. Will look into it
                print('TCP received "%s"' % [hex(ord(c)) for c in vcu_udp_received_message])


    client.publish(SUBSYSTEM, json.dumps(_state))

#needed for the interface, doesn't really do anything as of now
def on_message(client, topic, message):
    topic_components = message.topic.split("/")

    if topic_components[2] != "set":
        return

    json_message = json.loads(message.payload)
    print "Receieved mqtt message to set state to", json_message["t_state"]
    _state["t_state"] = json_message["t_state"]

    if _state["state"] != _state["t_state"]:
        transition(_state["state"], _state["t_state"], tcp_sock)

#keeping the same function map layout from other code because I like it
_possible_states = {
    "IDLE": idle_func,
    "HOMING": homing_func,
    "READY": ready_func,
    "RUNNING": running_func,
    "RUNNING_AND_LOGGING": running_and_logging_func,
    "FAULT": fault_func,
    "ESTOP": None
}


# Setup mqtt client
client = mqtt.Client()
print "Connecting to mqtt on", MQTT_IP
client.connect(MQTT_IP, 1883)
client.loop_start()
client.on_message = on_message
client.subscribe(SUBSYSTEM + "/#")

try:
    # Setup TCP and UDP connection to system
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print "Connecting by UDP on", SUSPENSION_IP
    udp_sock.bind(('', SUSPENSION_PORT))
    server_address = (SUSPENSION_IP, SUSPENSION_PORT)
    # udp_sock.settimeout(0.01) #10 ms

    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print "Connecting by TCP on", SUSPENSION_IP
    tcp_sock.connect((SUSPENSION_IP, SUSPENSION_PORT))
    # tcp_sock.settimeout(0.01) #10 ms
except socket.error, e:
    print "Error opening socket:", e
    quit()

print "Successfully Connected to SCU"
get_endianness()

while True:
    logic_loop(client, tcp_sock, udp_sock)

client.loop_stop()
