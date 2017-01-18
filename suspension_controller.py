#
# Example of sending message to SCU over TCP
#
#start_scu_message_req = struct.pack(network_endianness+'BB', 0x11, 0);
#tcp_sock.send(start_scu_message_req)

import json
import os
import paho.mqtt.client as mqtt
import socket
import time

SUBSYSTEM = "remote_subsystem/suspension"
MQTT_IP = '192.168.0.100'
SUSPENSION_IP = "192.168.0.10"
SUSPENSION_PORT = 3000

#keeping the same function map layout from other code because I like it
_states = {
    "IDLE": idle_func,
    "HOMING": homing_func,
    "READY": ready_func,
    "RUNNING": running_func,
    "RUNNING_AND_LOGGING": running_and_logging_func,
    "FAULT": fault_func,
    "ESTOP": None
}


# External and internal states
state = {
    "state": "IDLE",
    "target_state": "IDLE",
}


def idle_func(t, tcp_sock):
    if t == "READY":
        signal("START_SCU", tcp_sock)
        state["state"] = "HOMING"

#not sure how this will work since the system will go from
#idle to running through the intermediate states without
#any extra input from us
def homing_func(t, tcp_sock):
    if t == "READY":
        #have to check if the SCU is out of homing yet,
        #don't know how to do that yet
        if "some_conditional"
            state["state"] = "READY"

def ready_func(t, tcp_sock):
    if t == "RUNNING":
        signal("START_SCU", tcp_sock)
        state["state"] = "RUNNING"

def running_func(t, tcp_sock):
    if t == "READY":
        signal("STOP_SCU", tcp_sock)
        state["state"] = "READY"
    elif t == "RUNNING_AND_LOGGING":
        signal("START_SCU_LOGGING", tcp_sock)
        state["state"] = "RUNNING_AND_LOGGING"

def running_and_logging_func(t, tcp_sock):
    if t == "READY":
        signal("STOP_SCU", tcp_sock)
        state["state"] = "READY"
    elif t == "RUNNING":
        signal("STOP_SCU_LOGGING", tcp_sock)
        state["state"] = "RUNNING"

#actually need a fault transition in this one because
#their system will lock itself into FAULT state and
#not do anything until it receives ""
def fault_func(t, tcp_sock):
    signal("CLEAR_FAULT", tcp_sock)
    signal("STOP_SCU", tcp_sock)
    state["state"] = "READY"


#takes in a message from the list and actually sends the TCP communication,
#and waits for the response from the SCU
#might need to return True/False in the future idk
def signal(message, tcp_sock):
    if tcp_sock is None:
        return

    #see VCU_stub.py for wtf to do to send the message
    if message == "START_SCU":
        pass
    elif message == "STOP_SCU":
        pass
    elif message == "START_SCU_LOGGING":
        pass
    elif message == "STOP_SCU_LOGGING":
        pass
    elif message == "CLEAR_FAULT":
        pass
    else:
        print "[signal] Bad message"


#communicates over TCP to change system state from current_state to target_state
#might need to change later to have each transition function return whether
#it succeeded or not, like we do in the subsystem code
def transition(current_state, target_state, tcp_sock):
    _states[current_state](target_state, tcp_sock)
    if state[current_state] != target_state:
        transition(current_state, target_state, tcp_sock)


#pull status from TCP and UDP and send it out
def logic_loop(client, tcp_sock, udp_sock):
    #
    #read in state from AlesTech system over streaming UDP connection
    #TCP is only in response to us, so we will look for a TCP response
    #if we choose to send a message to the system
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

            #naturally prints will eventually be replaced with code for updating variables or something similar
            if (vcu_udp_received_message[0] == 0x21):
                vcu_udp_received_message =  struct.unpack_from(network_endianness+'BBfffffffHH', msg)
                print('SUSPENSION TRAVELS FL: %f FR: %f RL: %f RR: %f X Acc: %f Y Acc:  %f Z Acc:  %f Faults:  %d Status: %d' % vcu_udp_received_message[2:])
            elif (vcu_udp_received_message[0] == 0x22):
                vcu_udp_received_message =  struct.unpack_from(network_endianness+'BBffff', msg)
                print('PAD DISTANCES FL: %f FR Pad: %f RL: %f RR Pad: %f' % vcu_udp_received_message[2:])
            else:
                print('TCP received "%s"' % [hex(ord(c)) for c in vcu_udp_received_message])


    client.publish(SUBSYSTEM, json.dumps(state)) #push state according to system
    time.sleep(0.1)

#needed for the interface, doesn't really do anything as of now
def on_message(client, topic, message):
    message_components = message.split("/")
    if message_components[:-2] != "set":
        return

    state["target_state"] = message_components[:-1]

    if state["state"] != state["target_state"]:
        transition(state["state"], state["target_state"], tcp_sock)


# Setup mqtt client
client = mqtt.Client()
print "Connecting to mqtt on", MQTT_IP
client.connect(MQTT_IP, 1883)
client.loop_start()
client.on_message = on_message
client.subscribe(SUBSYSTEM + "/#")

# Setup TCP and UDP connection to system
udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print "Connecting by UDP on", SUSPENSION_IP
udp_sock.bind(('', SUSPENSION_PORT))
server_address = (SUSPENSION_IP, SUSPENSION_PORT)
udp_sock.settimeout(0.01) #10 ms

tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
print "Connecting by TCP on", SUSPENSION_IP
tcp_sock.connect((SUSPENSION_IP, SUSPENSION_PORT))
tcp_sock.settimeout(0.01) #10 ms

while True:
    logic_loop(client, tcp_sock, udp_sock)

client.loop_stop()
