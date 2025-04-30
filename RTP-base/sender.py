import argparse
import socket
import sys
import time
import select
from utils import PacketHeader, compute_checksum

def sender(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print("Starting sender\n")
    
    seq_num = 0
    window = {} 
    next_seq_num = 0
    base = 0  
    
    # Read data from stdin
    data = sys.stdin.buffer.read()
    print(f"Read {len(data)} bytes from stdin.")
    chunk_size = 1456  # 1472 - 16 bytes for header
    chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    print(f"Split data into {len(chunks)} chunks.") # Added print for clarity

    if not chunks and len(data) > 0:
        # This case should ideally not happen if data > 0 and chunk_size > 0
        print("Warning: Data read but resulted in no chunks. Check chunk_size.")

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

    def print_window_state():
        print(f"Window: base={base}, next_seq_num={next_seq_num}")
        print(f"Packets in window: {list(window.keys())}")
        sys.stdout.flush()

    
    # Send data
    while base < len(chunks) + 1:

        print_window_state() 
        # Send new packets if window allows
        while next_seq_num < base + window_size and next_seq_num <= len(chunks):
            data_header = PacketHeader(type=2, seq_num=next_seq_num, length=len(chunks[next_seq_num-1]))
            data_header.checksum = compute_checksum(data_header / chunks[next_seq_num-1])
            data_packet = bytes(data_header / chunks[next_seq_num-1])
            s.sendto(data_packet, (receiver_ip, receiver_port))
            window[next_seq_num] = (data_packet, time.time())
            print(f"Sending DATA packet {next_seq_num}, length={len(chunks[next_seq_num-1])}")

            if timer_start is None:
                timer_start = time.time()
            next_seq_num += 1

            sys.stdout.flush()
        
        # Check for ACKs
        try:
            ready = select.select([s], [], [], 0.1)
            if ready[0]:
                pkt, _ = s.recvfrom(1472)
                ack_header = PacketHeader(pkt[:16])
                print(f"ACK {ack_header.seq_num}")
                sys.stdout.flush()
                if ack_header.type == 3:
                    # Process cumulative ACK
                    if ack_header.seq_num > base:
                        # Remove acknowledged packets from window
                        for i in range(base, ack_header.seq_num):
                            if i in window:
                                del window[i]
                        base = ack_header.seq_num
                        # Reset timer if window moved
                        if window:
                            timer_start = time.time()
                        else:
                            timer_start = None
                print(f"Received ACK {ack_header.seq_num}")
                sys.stdout.flush()
        except (socket.error, BlockingIOError):
            pass
        
        # Check for timeout
        if timer_start is not None and time.time() - timer_start > 0.5:
            # Retransmit all packets in window
            for seq, (packet, _) in window.items():
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