import argparse
import socket
import sys
from utils import PacketHeader, compute_checksum

def receiver(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))
    print(f"Receiver listening on {receiver_ip}:{receiver_port}\n", file=sys.stderr)

    connection_active = False
    expected_seq = 0
    buffer = {}

    while True:
        pkt, addr = s.recvfrom(1472)
        hdr = PacketHeader(pkt[:16])
        msg = pkt[16:16+hdr.length]

        # START handshake (as before)
        if hdr.type == 0 and not connection_active:
            connection_active = True
            expected_seq = 1
            ack = PacketHeader(type=3, seq_num=1, length=0)
            ack.checksum = compute_checksum(ack / b'')
            s.sendto(bytes(ack / b''), addr)
            continue

        # DATA processing
        if hdr.type == 2 and connection_active:
            # checksum verify
            orig, hdr.checksum = hdr.checksum, 0
            if compute_checksum(hdr / msg) != orig:
                continue

            seq = hdr.seq_num
            # drop outside window
            if seq < expected_seq or seq >= expected_seq + window_size:
                continue
            buffer[seq] = msg

            # deliver in-order
            while expected_seq in buffer:
                sys.stdout.buffer.write(buffer.pop(expected_seq))
                expected_seq += 1

            # send cumulative ACK
            ack = PacketHeader(type=3, seq_num=expected_seq, length=0)
            ack.checksum = compute_checksum(ack / b'')
            s.sendto(bytes(ack / b''), addr)

        # (END handshake deferred to next commit)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip")
    parser.add_argument("receiver_port", type=int)
    parser.add_argument("window_size", type=int)
    args = parser.parse_args()
    receiver(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()
