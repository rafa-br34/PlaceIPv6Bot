import struct
from enum import IntEnum
from Networking import Utils


class Constants(IntEnum):
    ECHO_REQUEST = 128
    ECHO_REPLY = 129
    MULTICAST_LISTENER_QUERY = 130
    MULTICAST_LISTENER_REPORT = 131
    MULTICAST_LISTENER_DONE = 132
    ROUTER_SOLICITATION = 133
    ROUTER_ADVERTISEMENT = 134
    NEIGHBOR_SOLICITATION = 135
    NEIGHBOR_ADVERTISEMENT = 136
    REDIRECT_MESSAGE = 137
    ROUTER_RENUMBERING = 138
    ICMP_NODE_INFO_QUERY = 139
    ICMP_NODE_INFO_RESPONSE = 140
    INVERSE_NEIGHBOR_SOLICITATION = 141
    INVERSE_NEIGHBOR_ADVERTISEMENT = 142
    MULTICAST_LISTENER_DISCOVERY = 143
    HOME_AGENT_ADDRESS_DISCOVERY_REQUEST = 144
    HOME_AGENT_ADDRESS_DISCOVERY_REPLY = 145
    MOBILE_PREFIX_SOLICITATION = 146
    MOBILE_PREFIX_ADVERTISEMENT = 147
    CERTIFICATION_PATH_SOLICITATION = 148
    CERTIFICATION_PATH_ADVERTISEMENT = 149
    MULTICAST_ROUTER_ADVERTISEMENT = 151
    MULTICAST_ROUTER_SOLICITATION = 152
    MULTICAST_ROUTER_TERMINATION = 153
    RPL_CONTROL_MESSAGE = 155


def BuildPacket(Type, Code, Data):
    # TYPE(8) CODE(8) CHECKSUM(16)
    Header = struct.pack("!BBH", Type, Code, 0)
    Header = struct.pack("!BBH", Type, Code, Utils.CalculateChecksum(Header + Data))
    return Header + Data

def MakeEchoPacket(Identifier, Sequence, Data):
    return BuildPacket(Constants.ECHO_REQUEST, 0, struct.pack("!HH", Identifier, Sequence) + Data)