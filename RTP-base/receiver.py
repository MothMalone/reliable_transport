import argparse
import socket
import sys
from utils import PacketHeader, compute_checksum

def receiver(receiver_ip, receiver_port, window_size):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((receiver_ip, receiver_port))

    print(f"Receiver listening on {receiver_ip}:{receiver_port}\n", file=sys.stderr) 

    expected_seq_num = 0
    buffer = {}  # For out-of-order packets
    connection_active = False

    
    while True:
        pkt, address = s.recvfrom(1472)
        
        # Extract header and payload
        pkt_header = PacketHeader(pkt[:16])
        msg = pkt[16:16+pkt_header.length]

        print(f"\nReceived packet: type={pkt_header.type}, seq={pkt_header.seq_num}, len={pkt_header.length}", file=sys.stderr)

        # Verify checksum
        original_checksum = pkt_header.checksum
        pkt_header.checksum = 0
        computed_checksum = compute_checksum(pkt_header / msg)
        
        if original_checksum != computed_checksum:
            # Corrupted packet, ignore
            print(f"Checksum mismatch: got {original_checksum}, computed {computed_checksum}", file=sys.stderr)
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
            sys.stdout.flush()
            seq_num = pkt_header.seq_num

            print(f"Processing DATA packet {seq_num}, expecting {expected_seq_num}", file=sys.stderr)
            print(f"Buffer state: {sorted(buffer.keys())}", file=sys.stderr)

            
            # Drop packets outside the window
            if seq_num >= expected_seq_num + window_size:
                continue
                
            # Store the packet
            if seq_num >= expected_seq_num:
                buffer[seq_num] = msg
            
            # Process in-order packets
            while expected_seq_num in buffer:
                sys.stdout.buffer.write(buffer[expected_seq_num])
                sys.stdout.flush()
                del buffer[expected_seq_num]
                expected_seq_num += 1
            
            # Send cumulative ACK
            ack_header = PacketHeader(type=3, seq_num=expected_seq_num, length=0)
            ack_header.checksum = compute_checksum(ack_header / b'')
            s.sendto(bytes(ack_header / b''), address)

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