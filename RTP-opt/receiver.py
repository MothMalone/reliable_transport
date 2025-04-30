import argparse
import socket
import sys
from utils import PacketHeader, compute_checksum

def receiver(receiver_ip, receiver_port, window_size):
    # Create UDP socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))
    
    # Initialize variables
    expected_seq_num = 0
    buffer = {}  # For out-of-order packets
    connection_active = False
    
    while True:
        # Receive packet
        pkt, address = s.recvfrom(1472)
        
        # Extract header and payload
        pkt_header = PacketHeader(pkt[:16])
        msg = pkt[16:16+pkt_header.length]
        
        # Verify checksum
        original_checksum = pkt_header.checksum
        pkt_header.checksum = 0
        computed_checksum = compute_checksum(pkt_header / msg)
        
        if original_checksum != computed_checksum:
            # Corrupted packet, ignore
            continue
        
        # Process different packet types
        if pkt_header.type == 0:  # START
            if not connection_active:
                connection_active = True
                expected_seq_num = 1
                # Send ACK for START
                ack_header = PacketHeader(type=3, seq_num=1, length=0)
                ack_header.checksum = compute_checksum(ack_header / b'')
                s.sendto(bytes(ack_header / b''), address)
        
        elif pkt_header.type == 1:  # END
            if connection_active:
                # Send ACK for END
                ack_header = PacketHeader(type=3, seq_num=pkt_header.seq_num + 1, length=0)
                ack_header.checksum = compute_checksum(ack_header / b'')
                s.sendto(bytes(ack_header / b''), address)
                # Exit the connection
                break
        
        elif pkt_header.type == 2 and connection_active:  # DATA
            seq_num = pkt_header.seq_num
            
            # Drop packets outside the window
            if seq_num >= expected_seq_num + window_size:
                continue
                
            # Send individual ACK for this packet
            ack_header = PacketHeader(type=3, seq_num=seq_num, length=0)
            ack_header.checksum = compute_checksum(ack_header / b'')
            s.sendto(bytes(ack_header / b''), address)
            
            # Store the packet if not already processed
            if seq_num >= expected_seq_num:
                buffer[seq_num] = msg
            
            # Process in-order packets
            while expected_seq_num in buffer:
                sys.stdout.buffer.write(buffer[expected_seq_num])
                sys.stdout.flush()
                del buffer[expected_seq_num]
                expected_seq_num += 1

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

    receiver(args.receiver_ip, args.receiver_port, args.window_size)

if __name__ == "__main__":
    main()