import argparse
import socket
import sys
from utils import PacketHeader, compute_checksum

def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Starting sender\n")

    # Read all data from stdin (we won't actually send DATA yet)
    data = sys.stdin.buffer.read()
    print(f"Read {len(data)} bytes from stdin.")

    # Send START packet
    start_header = PacketHeader(type=0, seq_num=0, length=0)
    start_header.checksum = compute_checksum(start_header / b'')
    start_packet = bytes(start_header / b'')
    s.sendto(start_packet, (receiver_ip, receiver_port))
    print("Sent START")

    # Wait for START ACK
    s.settimeout(1)
    try:
        pkt, _ = s.recvfrom(1472)
        ack_header = PacketHeader(pkt[:16])
        if ack_header.type == 3 and ack_header.seq_num == 1:
            print("Received START ACK")
        else:
            print("Did not receive proper START ACK")
    except socket.timeout:
        print("Timeout waiting for START ACK")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip")
    parser.add_argument("receiver_port", type=int)
    parser.add_argument("window_size", type=int)
    args = parser.parse_args()
    sender(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()
