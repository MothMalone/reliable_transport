import argparse
import socket
import sys
from utils import PacketHeader, compute_checksum

def receiver(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))

    expected = 1
    buffer = {}    # seq_num → payload bytes
    connection_active = False

    while True:
        pkt, addr = s.recvfrom(1472)
        hdr = PacketHeader(pkt[:16])
        data = pkt[16:16+hdr.length]

        # checksum
        orig = hdr.checksum; hdr.checksum = 0
        if compute_checksum(hdr / data) != orig:
            continue

        if hdr.type == 0 and not connection_active:
            # START
            connection_active = True
            ack = PacketHeader(type=3, seq_num=1, length=0)
            ack.checksum = compute_checksum(ack / b'')
            s.sendto(bytes(ack / b''), addr)

        elif hdr.type == 2 and connection_active:
            seq = hdr.seq_num
            # drop if outside [expected, expected+window_size)
            if seq < expected or seq >= expected + window_size:
                continue

            # send individual ACK
            ack = PacketHeader(type=3, seq_num=seq, length=0)
            ack.checksum = compute_checksum(ack / b'')
            s.sendto(bytes(ack / b''), addr)

            # buffer & deliver in order
            if seq not in buffer:
                buffer[seq] = data
            while expected in buffer:
                sys.stdout.buffer.write(buffer.pop(expected))
                sys.stdout.flush()
                expected += 1

        elif hdr.type == 1 and connection_active:
            # END
            ack = PacketHeader(type=3, seq_num=hdr.seq_num+1, length=0)
            ack.checksum = compute_checksum(ack / b'')
            s.sendto(bytes(ack / b''), addr)
            break

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("receiver_ip"); p.add_argument("receiver_port", type=int)
    p.add_argument("window_size", type=int)
    args = p.parse_args()
    receiver(args.receiver_ip, args.receiver_port, args.window_size)
