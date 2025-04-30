import argparse
import socket
import sys
import time
import select
from utils import PacketHeader, compute_checksum

def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Starting sender\n")

    # Read data and split into chunks
    data = sys.stdin.buffer.read()
    chunk_size = 1456
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

    # START handshake (as before)
    start_hdr = PacketHeader(type=0, seq_num=0, length=0)
    start_hdr.checksum = compute_checksum(start_hdr / b'')
    s.sendto(bytes(start_hdr / b''), (receiver_ip, receiver_port))
    s.settimeout(1)
    try:
        pkt, _ = s.recvfrom(1472)
        ack = PacketHeader(pkt[:16])
        if ack.type != 3 or ack.seq_num != 1:
            return
    except socket.timeout:
        return

    # Set up sliding window
    s.setblocking(False)
    base = next_seq = 1
    window = {}
    timer_start = None

    def send_data(seq):
        hdr = PacketHeader(type=2, seq_num=seq, length=len(chunks[seq-1]))
        hdr.checksum = compute_checksum(hdr / chunks[seq-1])
        pkt = bytes(hdr / chunks[seq-1])
        s.sendto(pkt, (receiver_ip, receiver_port))
        window[seq] = (pkt, time.time())
        print(f"Sent DATA {seq}")

    # Main send loop
    while base <= len(chunks):
        # fill window
        while next_seq < base + window_size and next_seq <= len(chunks):
            send_data(next_seq)
            if timer_start is None:
                timer_start = time.time()
            next_seq += 1

        # check ACKs
        try:
            ready, _, _ = select.select([s], [], [], 0.1)
            if ready:
                pkt, _ = s.recvfrom(1472)
                ack = PacketHeader(pkt[:16])
                if ack.type == 3 and ack.seq_num > base:
                    for i in range(base, ack.seq_num):
                        window.pop(i, None)
                    base = ack.seq_num
                    timer_start = time.time() if window else None
                    print(f"Moved base to {base}")
        except:
            pass

        # timeout -> retransmit
        if timer_start and time.time() - timer_start > 0.5:
            for seq, (pkt, _) in window.items():
                s.sendto(pkt, (receiver_ip, receiver_port))
                print(f"Retransmitted DATA {seq}")
            timer_start = time.time()

    # (END handshake deferred to next commit)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receiver_ip")
    parser.add_argument("receiver_port", type=int)
    parser.add_argument("window_size", type=int)
    args = parser.parse_args()
    sender(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()
