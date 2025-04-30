import argparse
import socket
import sys
import time
import select
from utils import PacketHeader, compute_checksum

def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Starting sender\n")

    # Read and chunk data
    data = sys.stdin.buffer.read()
    chunk_size = 1456
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]

    # START handshake
    start_hdr = PacketHeader(type=0, seq_num=0, length=0)
    start_hdr.checksum = compute_checksum(start_hdr / b'')
    s.sendto(bytes(start_hdr / b''), (receiver_ip, receiver_port))
    s.settimeout(1)
    try:
        pkt, _ = s.recvfrom(1472)
        ack = PacketHeader(pkt[:16])
        if ack.type != 3 or ack.seq_num != 1:
            print("Bad START ACK"); return
    except socket.timeout:
        print("Timeout on START"); return

    # SR window bookkeeping
    s.setblocking(False)
    base = next_seq = 1
    window = {}  # seq_num → (packet_bytes, send_time, acked_flag)
    timer_start = {}

    # send_data helper
    def send_pkt(seq):
        hdr = PacketHeader(type=2, seq_num=seq, length=len(chunks[seq-1]))
        hdr.checksum = compute_checksum(hdr / chunks[seq-1])
        pkt = bytes(hdr / chunks[seq-1])
        s.sendto(pkt, (receiver_ip, receiver_port))
        window[seq] = (pkt, time.time(), False)
        timer_start[seq] = time.time()
        print(f"Sent DATA {seq}")

    # send as far as window allows
    while base <= len(chunks):
        while next_seq < base + window_size and next_seq <= len(chunks):
            send_pkt(next_seq)
            next_seq += 1

        # handle incoming individual ACKs
        try:
            ready, _, _ = select.select([s], [], [], 0.1)
            if ready:
                pkt, _ = s.recvfrom(1472)
                ack = PacketHeader(pkt[:16])
                if ack.type == 3 and ack.seq_num in window:
                    _, _, _ = window[ack.seq_num]
                    window[ack.seq_num] = (window[ack.seq_num][0],
                                           window[ack.seq_num][1],
                                           True)
                    print(f"ACK {ack.seq_num}")
                    # advance base past any acked packets
                    while base in window and window[base][2]:
                        del window[base]
                        base += 1
        except (BlockingIOError, socket.error):
            pass

    # END handshake
    end_hdr = PacketHeader(type=1, seq_num=next_seq-1, length=0)
    end_hdr.checksum = compute_checksum(end_hdr / b'')
    s.sendto(bytes(end_hdr / b''), (receiver_ip, receiver_port))
    s.settimeout(0.5)
    try:
        pkt, _ = s.recvfrom(1472)
        ack = PacketHeader(pkt[:16])
        if ack.type == 3 and ack.seq_num == next_seq:
            print("Received END ACK")
    except socket.timeout:
        pass

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("receiver_ip"); p.add_argument("receiver_port", type=int)
    p.add_argument("window_size", type=int)
    args = p.parse_args()
    sender(args.receiver_ip, args.receiver_port, args.window_size)
