class Traceroute(NetworkApplication):

    # Function to receive a single ping response
    def receiveOnePing(self, icmpSocket, timeout, time_of_sending):
        """
        Wait for a reply from the destination, process the ICMP packet, and compute the delay.
        Arguments:
            icmpSocket -- the socket used to send/receive ICMP packets
            timeout -- time (in seconds) to wait for a response
            time_of_sending -- the time at which the ping was sent
        Returns:
            A tuple (total_delay, icmp_type), where total_delay is the round-trip time in milliseconds
            and icmp_type is the type of ICMP response received.
        """
        while True:
            # Wait for the socket to become ready to read (or timeout)
            ready = select.select([icmpSocket], [], [], timeout)
            if ready[0] == []:  # If no data is received within the timeout period
                return None, None  # Return None to indicate a timeout

            time_of_receipt = time.time()  # Record the time the response is received
            received_packet, destinationAddress = icmpSocket.recvfrom(1024)  # Receive the packet
            # Extract the ICMP header from the IP packet (bytes 20 to 28)
            header = received_packet[20:28]
            # Unpack the ICMP header into its fields (type, code, checksum, ID, sequence)
            icmp_type, code, checksum, packet_ID, sequence = struct.unpack("bbHHh", header)
            # Calculate the total round-trip delay in milliseconds
            total_delay = (time_of_receipt - time_of_sending) * 1000
            # Return the total delay and the ICMP type (to determine if it's an Echo Reply)
            return total_delay, icmp_type

    # Function to send a single ICMP Echo Request (ping)
    def sendOnePing(self, icmpSocket, destinationAddress, ID, ttl):
        """
        Send one ICMP Echo Request to the destination with a specified TTL (Time-to-Live).
        Arguments:
            icmpSocket -- the socket used to send the ICMP packet
            destinationAddress -- the IP address of the target
            ID -- a unique identifier for the packet
            ttl -- the time-to-live (number of hops before the packet is discarded)
        Returns:
            A tuple (time_of_sending, packet_length), where time_of_sending is the time the packet was sent,
            and packet_length is the length of the data being sent.
        """
        # Set the TTL (time-to-live) value for the packet
        icmpSocket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)

        # Create an ICMP header for the Echo Request (type=8, code=0)
        header = struct.pack("bbHHh", 8, 0, 0, ID, 1)
        # Add a timestamp to the packet data
        data = struct.pack("d", time.time())
        # Calculate the checksum of the packet (header + data)
        checksum = self.checksum(header + data)
        # Recreate the header with the correct checksum
        header = struct.pack("bbHHh", 8, 0, checksum, ID, 1)
        # Combine the header and data into a complete packet
        packet = header + data
        # Send the packet to the destination address
        icmpSocket.sendto(packet, (destinationAddress, 1))
        # Record the time of sending to calculate the round-trip time later
        time_of_sending = time.time()
        # Return the time of sending and the length of the packet data
        packet_length = len(data)
        return time_of_sending, packet_length

    # Function to perform one trace step (send and receive one ping)
    def doOneTrace(self, destinationAddress, timeout, ttl):
        """
        Perform a single trace step by sending one ICMP Echo Request and receiving a reply.
        Arguments:
            destinationAddress -- the IP address of the target
            timeout -- time (in seconds) to wait for a response
            ttl -- time-to-live value for the packet
        Returns:
            A tuple (icmp_type, delay, packet_length), where icmp_type is the type of ICMP response,
            delay is the round-trip time in milliseconds, and packet_length is the length of the data sent.
        """
        # Get the protocol number for ICMP
        icmp = socket.getprotobyname("icmp")
        try:
            # Create a raw socket for sending and receiving ICMP packets
            icmpSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
        except socket.error as e:
            # Handle errors in socket creation
            print("Error creating socket: %s" % e)
            sys.exit(1)

        # Generate a unique ID for the packet (based on the timeout and current time)
        ID = int((id(timeout) * time.time()) % 65535)
        # Send one ping to the destination and record the time of sending
        time_of_sending, packet_length = self.sendOnePing(icmpSocket, destinationAddress, ID, ttl)
        # Receive the ping response and calculate the delay
        delay, icmp_type = self.receiveOnePing(icmpSocket, timeout, time_of_sending)
        # Close the socket after the trace step is completed
        icmpSocket.close()
        # Return the ICMP type, the round-trip delay, and the packet length
        return icmp_type, delay, packet_length

    # Constructor to initialize and run the traceroute
    def __init__(self, args):
        """
        Initialize the traceroute by resolving the target hostname and iteratively sending pings.
        Arguments:
            args -- command-line arguments containing the hostname and other options.
        """
        # Print the target hostname
        print('Traceroute to: %s...' % (args.hostname))
        # Resolve the hostname to an IP address
        ip_address = socket.gethostbyname(args.hostname)
        ttl = 1  # Start the TTL (time-to-live) value at 1
        icmp_type = None  # Initialize the ICMP type variable

        # Continue tracing until an ICMP Echo Reply (type 0) is received
        while icmp_type != 0:
            # Perform one trace step (send and receive one ping)
            icmp_type, delay, packet_length = self.doOneTrace(ip_address, 4, ttl)
            if delay is None:  # If no response is received (timeout)
                print("Timeout")  # Print a timeout message
            else:
                # Print the results for this hop
                self.printOneResult(ip_address, packet_length, delay, ttl, args.hostname)
            ttl += 1  # Increment the TTL for the next hop
