import socket
import struct
import time
import os
import select

# ICMP packet constants
ICMP_ECHO_REQUEST = 8  # Echo request (type 8 for ping)
ICMP_ECHO_REPLY = 0    # Echo reply (type 0 for ping reply)
ICMP_CODE = socket.getprotobyname('icmp')  # Protocol number for ICMP

# Checksum function for calculating the checksum of an ICMP packet
def checksum(source_string):
    """
    Compute the checksum for the given data (source_string).
    This is used to verify data integrity for ICMP packets.
    """
    count_to = (len(source_string) // 2) * 2  # Process data in 2-byte chunks
    summation = 0  # Initialize sum
    count = 0  # Counter to iterate through the data

    # Sum all the 16-bit chunks
    while count < count_to:
        this_val = source_string[count + 1] * 256 + source_string[count]
        summation = summation + this_val
        summation = summation & 0xffffffff  # Keep summation within 32 bits
        count = count + 2

    # If there's an odd byte at the end, add it separately
    if count_to < len(source_string):
        summation = summation + source_string[len(source_string) - 1]
        summation = summation & 0xffffffff

    # Add high 16 bits to low 16 bits
    summation = (summation >> 16) + (summation & 0xffff)
    summation = summation + (summation >> 16)
    
    # One's complement and mask to 16 bits
    answer = ~summation
    answer = answer & 0xffff
    answer = answer >> 8 | (answer << 8 & 0xff00)
    return answer


class ICMPPing:
    
    # Function to receive a ping response
    def receiveOnePing(self, icmpSocket, destinationAddress, ID, timeout):
        """
        Receive the ICMP reply (ping response).
        Arguments:
            icmpSocket -- the socket used to send/receive ICMP packets
            destinationAddress -- the target IP address
            ID -- the identifier used to match requests and responses
            timeout -- time to wait for a response (in seconds)
        Returns:
            The time delay (in seconds) if the packet is received successfully, else None on timeout.
        """
        time_remaining = timeout  # Time left to wait for a response
        while True:
            start_time = time.time()  # Record the time at the start of waiting
            # Check if socket is ready to receive within the remaining time
            ready = select.select([icmpSocket], [], [], time_remaining)
            time_spent = time.time() - start_time  # Calculate time spent waiting

            if ready[0] == []:  # Timeout occurred (no packet received)
                return None

            time_received = time.time()  # Record the time when the packet was received
            rec_packet, addr = icmpSocket.recvfrom(1024)  # Receive packet

            # Extract ICMP header from the received packet (skip IP header, first 20 bytes)
            icmp_header = rec_packet[20:28]
            type, code, checksum, packet_ID, sequence = struct.unpack("bbHHh", icmp_header)

            # Check if the received packet has the correct ID (to match the sent request)
            if packet_ID == ID:
                # Unpack the timestamp sent with the packet
                time_sent = struct.unpack("d", rec_packet[28:28 + struct.calcsize("d")])[0]
                # Return the delay between sending and receiving the packet
                return time_received - time_sent

            # Adjust the remaining time to wait after each iteration
            time_remaining = time_remaining - time_spent
            if time_remaining <= 0:
                return None

    # Function to send an ICMP Echo Request
    def sendOnePing(self, icmpSocket, destinationAddress, ID):
        """
        Send one ICMP Echo Request (ping).
        Arguments:
            icmpSocket -- the socket used to send the ICMP request
            destinationAddress -- the target IP address
            ID -- the identifier used to match requests and responses
        """
        # Create an ICMP header with type=8 (Echo Request), code=0, and a dummy checksum
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, 0, ID, 1)
        # Add current timestamp to the data payload (used to calculate round-trip time)
        data = struct.pack("d", time.time())

        # Calculate the checksum for the packet (header + data)
        packet_checksum = checksum(header + data)

        # Rebuild the ICMP header with the correct checksum
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, packet_checksum, ID, 1)
        packet = header + data  # Complete the packet (header + data)

        # Send the packet to the destination address
        icmpSocket.sendto(packet, (destinationAddress, 1))

    # Function to perform one ping
    def doOnePing(self, destinationAddress, timeout):
        """
        Perform one ping to the destination.
        Arguments:
            destinationAddress -- the target IP address
            timeout -- time to wait for a response (in seconds)
        Returns:
            The time delay for the ping or None if it timed out.
        """
        # Create a raw socket to send and receive ICMP packets
        icmpSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, ICMP_CODE)
        ID = os.getpid() & 0xFFFF  # Use the process ID as the packet ID

        # Send the ICMP Echo Request
        self.sendOnePing(icmpSocket, destinationAddress, ID)
        # Receive the ICMP Echo Reply and calculate the delay
        delay = self.receiveOnePing(icmpSocket, destinationAddress, ID, timeout)

        icmpSocket.close()  # Close the socket after use
        return delay

    # Function to display the result of a ping
    def printOneResult(self, destinationAddress, ttl, delay, packet_size):
        """
        Display the result of a ping.
        Arguments:
            destinationAddress -- the target IP address
            ttl -- time-to-live (hop limit)
            delay -- the round-trip time (in seconds)
            packet_size -- the size of the ICMP packet sent
        """
        if delay is None:
            print(f"Request timed out.")  # If no response was received
        else:
            delay = delay * 1000  # Convert delay to milliseconds
            print(f"{packet_size} bytes from {destinationAddress}: ttl={ttl} time={delay:.2f} ms")

    # Constructor that initializes the ping process
    def __init__(self, hostname, timeout=1, count=4):
        """
        Initialize the ICMPPing instance and start sending pings.
        Arguments:
            hostname -- the target hostname (or IP address)
            timeout -- maximum time to wait for each ping response (in seconds)
            count -- number of pings to send
        """
        # Resolve the hostname to its IP address
        destinationAddress = socket.gethostbyname(hostname)
        print(f"Ping to {hostname} [{destinationAddress}] with {count} packets:")

        # Loop to send the specified number of pings
        for i in range(count):
            # Send one ping and measure the delay
            delay = self.doOnePing(destinationAddress, timeout)
            if delay is None:
                # If the ping timed out, print timeout message
                self.printOneResult(destinationAddress, 0, None, 64)
            else:
                # If successful, print the result (assuming TTL=64 and packet size=64 bytes)
                self.printOneResult(destinationAddress, 64, delay, 64)
            time.sleep(1)  # Wait for 1 second before sending the next ping


if __name__ == "__main__":
    # Initialize the ICMPPing class with the target hostname (e.g., google.com)
    ping = ICMPPing("google.com")
