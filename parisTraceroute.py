class ParisTraceroute(NetworkApplication):
    
    # Function to receive a single ping response
    def receiveOnePing(self, icmpSocket, timeout, timeOfSending):
        """
        Wait to receive a response from the socket after sending a ping.
        Arguments:
            icmpSocket -- the socket used to send/receive ICMP packets
            timeout -- time (in seconds) to wait for a response
            timeOfSending -- the time at which the ping was sent
        Returns:
            A tuple of (delay, address), where delay is the round-trip time in milliseconds,
            and address is the sender's address. Returns (None, None) on timeout.
        """
        while True:
            # Wait for the socket to be ready to receive data
            ready = select.select([icmpSocket], [], [], timeout)
            if ready[0] == []:  # If nothing is received before timeout, return None
                return None, None
            timeOfReceipt = time.time()  # Record the time the response is received
            recvdPacket, address = icmpSocket.recvfrom(1024)  # Receive the packet and address
            delay = (timeOfReceipt - timeOfSending) * 1000  # Calculate the delay in milliseconds
            return delay, address  # Return the delay and the address from which the packet was received

    # Function to send a single ping (ICMP or UDP)
    def sendOnePing(self, icmpSocket, destinationAddress, ID, ttl, protocol):
        """
        Send a ping (ICMP Echo Request or UDP) to the destination.
        Arguments:
            icmpSocket -- the socket used to send the packet
            destinationAddress -- the target IP address
            ID -- an identifier for the packet (to match with replies)
            ttl -- time-to-live value (number of hops before the packet is discarded)
            protocol -- "ICMP" or "UDP", specifies the type of packet to send
        Returns:
            The time the packet was sent.
        """
        # Set the TTL (time-to-live) for the socket
        icmpSocket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)

        if protocol == "ICMP":
            # Create an ICMP header (type=8 for Echo Request)
            header = struct.pack("bbHHh", 8, 0, 0, ID, 1)
            data = struct.pack("d", time.time())  # Timestamp for the packet
            checksum = self.checksum(header + data)  # Compute the checksum
            packet = header + data  # Combine header and data into one packet
            # Update the ICMP header with the correct checksum
            header = struct.pack("bbHHh", 8, 0, checksum, ID, 1)
            # Send the packet to the destination address
            icmpSocket.sendto(packet, (destinationAddress, 1))
            timeOfSending = time.time()  # Record the time the packet is sent

        else:  # If protocol is UDP
            # Create a UDP header with random source port and destination port 33434 (for traceroute)
            header = struct.pack("!HHHH", 0, 33434, 0, 0)
            data = struct.pack("d", time.time())  # Timestamp for the packet
            checksum = self.checksum(header + data)  # Compute the checksum
            packet = header + data  # Combine header and data
            # Get the source port from the socket
            sourcePort = icmpSocket.getsockname()[1]
            # Update the UDP header with source port, destination port, length, and checksum
            header = struct.pack('!HHHH', sourcePort, 33434, len(packet), checksum)
            # Send the UDP packet to the destination address
            icmpSocket.sendto(packet, (destinationAddress, 33434))
            timeOfSending = time.time()  # Record the time the packet is sent

        return timeOfSending  # Return the time of sending

    # Function to perform one trace step
    def doOneTrace(self, destinationAddress, timeout, ttl, protocol):
        """
        Perform one trace to the destination by sending multiple pings and measuring the delay.
        Arguments:
            destinationAddress -- the target IP address
            timeout -- time (in seconds) to wait for a response
            ttl -- time-to-live value for the packet
            protocol -- "ICMP" or "UDP", specifies the type of packet to send
        Returns:
            A tuple (delays, address, packetLoss), where delays is a list of round-trip times (in milliseconds),
            address is the sender's address, and packetLoss is the percentage of lost packets.
        """
        try:
            # Create a raw socket for ICMP or UDP
            if protocol == "ICMP":
                icmp = socket.getprotobyname("icmp")
                icmpSocket = socket.socket(socket.AF_INET, socket.SOCK_RAW, icmp)
            elif protocol == "UDP":
                udp = socket.getprotobyname("udp")
                icmpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, udp)
            else:
                print("Please input a valid protocol (ICMP or UDP)")
                sys.exit(1)  # Exit if the protocol is invalid
        except socket.error as e:
            print(f"Socket error: {e}")  # Handle socket errors
            sys.exit(1)

        delays = []  # List to store delays
        packetsSent = 0  # Count of packets sent
        packetsReceived = 0  # Count of packets received
        ID = int((id(timeout) * time.time()) % 65535)  # Generate a unique packet ID

        # Send 3 pings for each trace step
        for i in range(3):
            timeOfSending = self.sendOnePing(icmpSocket, destinationAddress, ID, ttl, protocol)  # Send a ping
            packetsSent += 1
            # Receive the ping response and calculate the delay
            delay, address = self.receiveOnePing(icmpSocket, timeout, timeOfSending)
            if delay is None:  # If no response is received (timeout)
                print("Timeout")
                sys.exit(1)  # Exit on timeout
            else:
                packetsReceived += 1  # Increment the count of received packets
                delays.append(delay)  # Add the delay to the list

        icmpSocket.close()  # Close the socket after use

        # Calculate packet loss percentage
        if packetsSent > 0:
            packetLoss = ((packetsSent - packetsReceived) / packetsSent) * 100

        return delays, address, packetLoss  # Return the delays, address, and packet loss

    # Constructor to initialize the traceroute and perform the trace
    def __init__(self, args):
        """
        Initialize the Paris-Traceroute by resolving the target hostname and iteratively sending pings.
        Arguments:
            args -- command-line arguments containing the hostname, timeout, and protocol.
        """
        print('Paris-Traceroute to: %s...' % (args.hostname))  # Print the target hostname
        destination_ip = socket.gethostbyname(args.hostname)  # Resolve the hostname to an IP address
        ttl = 1  # Start with a TTL (time-to-live) value of 1
        ip = None  # Initialize the current hop's IP

        # Continue sending pings until the destination IP is reached
        while ip != destination_ip:
            # Perform one trace step (send pings with the current TTL)
            delays, address, packet_loss = self.doOneTrace(destination_ip, args.timeout, ttl, args.protocol)
            ip = address[0]  # Extract the IP address from the response

            try:
                # Try to resolve the IP address to a hostname
                host = socket.gethostbyaddr(ip)
                print("%s: " % (host[0]))  # Print the resolved hostname
            except:
                print("Hostname not available")  # Print if the hostname cannot be resolved

            # Print the results for this hop
            self.printMultipleResults(ttl, ip, delays, args.hostname)
            # Calculate min, max, and average delays
            minDelay = min(delays)
            maxDelay = max(delays)
            avgDelay = sum(delays) / len(delays)
            # Print additional details such as packet loss and delays
            self.printAdditionalDetails(packet_loss, minDelay, avgDelay, maxDelay)
            print('\n')  # Print a newline between hops
            ttl += 1  # Increment the TTL for the next hop
            time.sleep(1)  # Wait 1 second before sending the next packet
