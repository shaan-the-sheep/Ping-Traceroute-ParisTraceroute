class Proxy(NetworkApplication):
    def __init__(self, args):
        print('Web Proxy starting on port: %i...' % (args.port))
        self.cache = {}
        serverSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serverAddr = ('', args.port)
        serverSock.bind(serverAddr)
        serverSock.listen(1)
        while True:
            clientSock, addr = serverSock.accept()
            t = threading.Thread(target=self.handleRequest, args=(clientSock,))
            t.start()

    def handleRequest(self, tcpSocket):
        request = tcpSocket.recv(1024).decode()
        print(request)
        requestType = request.split()[0]
        path = request.split()[1]
        header = ''
        for line in request.split('\r\n')[0:]:
            header += line + '\n'
        try:
            if requestType == 'GET':
                # if path is file stored locally
                if os.path.exists('.' + path):
                    if path in self.cache:
                        content = self.cache[path]
                    else:
                        with open('.' + path, 'rb') as f:
                            content = f.read()
                            self.cache[path] = content
                    statusLine = 'HTTP/1.1 200 OK\r\n\r\n'
                    response = statusLine.encode() + header.encode() + content
                    tcpSocket.sendall(response)
                else:
                    # if path is url to web page
                    if path in self.cache:
                        content = self.cache[path]
                    else:
                        # fetch page from server
                        webSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        webSock.connect((path.split('/')[2], 80))
                        webSock.sendall(request.encode())
                        response = webSock.recv(1024)
                        content = b''
                        while response:
                            content += response
                            response = webSock.recv(1024)
                        self.cache[path] = content
                    statusLine = 'HTTP/1.1 200 OK\r\n\r\n'
                    response = statusLine.encode() + header.encode() + content
                    tcpSocket.sendall(response)

            elif requestType == 'POST' or requestType == 'PUT':
                content_length = int(request.split('Content-Length: ')[1].split('\r\n')[0])
                content = tcpSocket.recv(content_length)
                # Forward the request to the web
                webSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                webSock.connect((path.split('/')[2], 80))
                statusLine = 'HTTP/1.1 200 OK\r\n\r\n'
                response = statusLine.encode() + header.encode() + content
                webSock.sendall(response)
                response = webSock.recv(1024)
                while response:
                    tcpSocket.sendall(response)
                    response = webSock.recv(1024)
                return

            elif requestType == 'DELETE':
                # Delete the file if it exists
                if os.path.isfile('.' + path):
                    os.remove('.' + path)
                    if path in self.cache:
                        del self.cache[path]
                    statusLine = b'HTTP/1.1 200 OK\r\n\r\nFile deleted'
                else:
                    statusLine = b'HTTP/1.1 404 Not Found\r\n\r\nFile Not Found'
                response = statusLine.encode() + header.encode()
                tcpSocket.sendall(response)
                return

            else:
                raise Exception('Unsupported method')

        except Exception as e:
            response = b'HTTP/1.1 400 Bad Request\r\n\r\n' + str(e).encode()
            tcpSocket.sendall(response)
            
        tcpSocket.close()
