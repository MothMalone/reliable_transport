import argparse
import socket
import sys
from utils import PacketHeader, compute_checksum

def receiver(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))
    print(f"Receiver listening on {receiver_ip}:{receiver_port}\n", file=sys.stderr)

    connection_active = False

    while True:
        pkt, addr = s.recvfrom(1472)
        header = PacketHeader(pkt[:16])

        if header.type == 0 and not connection_active:
            # START received
            connection_active = True
            expected_seq = 1
            # Reply with START ACK (seq 1)
            ack = PacketHeader(type=3, seq_num=1, length=0)
            ack.checksum = compute_checksum(ack / b'')
            s.sendto(bytes(ack / b''), addr)
            print("Sent START ACK", file=sys.stderr)
            # After this commit, we can exit
            break

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip")
    parser.add_argument("receiver_port", type=int)
    parser.add_argument("window_size", type=int)
    args = parser.parse_args()
    receiver(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()
