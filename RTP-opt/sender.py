import argparse
import socket
import sys
import time
import select
from utils import PacketHeader, compute_checksum

def sender(receiver_ip, receiver_port, window_size):
    # Create UDP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # Initialize variables
    seq_num = 0
    window = {}  # Maps sequence numbers to (packet, sent_time, acked)
    next_seq_num = 0
    base = 0  # Base of the window
    
    # Read data from stdin
    data = sys.stdin.buffer.read()
    chunk_size = 1456  # 1472 - 16 bytes for header
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    
    # Send START packet
    start_header = PacketHeader(type=0, seq_num=seq_num, length=0)
    start_header.checksum = compute_checksum(start_header / b'')
    start_packet = bytes(start_header / b'')
    s.sendto(start_packet, (receiver_ip, receiver_port))
    
    # Wait for START ACK
    s.settimeout(1)
    try:
        pkt, _ = s.recvfrom(1472)
        ack_header = PacketHeader(pkt[:16])
        if ack_header.type != 3 or ack_header.seq_num != 1:
            print("Did not receive proper START ACK")
            return
    except socket.timeout:
        print("Timeout waiting for START ACK")
        return
    
    # Set non-blocking mode for socket
    s.setblocking(False)
    
    # Initialize sequence number
    seq_num = 1
    base = 1
    next_seq_num = 1
    timer_start = None
    
    # Send data
    while base < len(chunks) + 1:
        # Send new packets if window allows
        while next_seq_num < base + window_size and next_seq_num < len(chunks) + 1:
            data_header = PacketHeader(type=2, seq_num=next_seq_num, length=len(chunks[next_seq_num-1]))
            data_header.checksum = compute_checksum(data_header / chunks[next_seq_num-1])
            data_packet = bytes(data_header / chunks[next_seq_num-1])
            s.sendto(data_packet, (receiver_ip, receiver_port))
            window[next_seq_num] = (data_packet, time.time(), False)  # Not acked yet
            if timer_start is None:
                timer_start = time.time()
            next_seq_num += 1
        
        # Check for ACKs
        try:
            ready = select.select([s], [], [], 0.1)
            if ready[0]:
                pkt, _ = s.recvfrom(1472)
                ack_header = PacketHeader(pkt[:16])
                if ack_header.type == 3:
                    # Process individual ACK
                    acked_seq = ack_header.seq_num
                    if acked_seq in window:
                        packet, sent_time, _ = window[acked_seq]
                        window[acked_seq] = (packet, sent_time, True)  # Mark as acked
                    
                    # Update base (smallest unacked packet)
                    while base in window and window[base][2]:  # If base is acked
                        del window[base]
                        base += 1
                    
                    # Reset timer if window moved
                    if window:
                        # Only restart timer if there are unacked packets
                        unacked = False
                        for _, _, acked in window.values():
                            if not acked:
                                unacked = True
                                break
                        if unacked:
                            timer_start = time.time()
                        else:
                            timer_start = None
                    else:
                        timer_start = None
        except (socket.error, BlockingIOError):
            pass
        
        # Check for timeout
        if timer_start is not None and time.time() - timer_start > 0.5:
            # Retransmit only unacked packets in window
            for seq, (packet, _, acked) in window.items():
                if not acked:
                    s.sendto(packet, (receiver_ip, receiver_port))
            timer_start = time.time()
    
    # Send END packet
    end_header = PacketHeader(type=1, seq_num=seq_num, length=0)
    end_header.checksum = compute_checksum(end_header / b'')
    end_packet = bytes(end_header / b'')
    s.sendto(end_packet, (receiver_ip, receiver_port))
    
    # Wait for END ACK with 500ms timeout
    end_time = time.time() + 0.5
    while time.time() < end_time:
        try:
            ready = select.select([s], [], [], end_time - time.time())
            if ready[0]:
                pkt, _ = s.recvfrom(1472)
                ack_header = PacketHeader(pkt[:16])
                if ack_header.type == 3 and ack_header.seq_num == seq_num + 1:
                    break  # Received END ACK
        except (socket.error, BlockingIOError):
            pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "receiver_ip", help="The IP address of the host that receiver is running on"
    )
    parser.add_argument(
        "receiver_port", type=int, help="The port number on which receiver is listening"
    )
    parser.add_argument(
        "window_size", type=int, help="Maximum number of outstanding packets"
    )
    args = parser.parse_args()

    sender(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()