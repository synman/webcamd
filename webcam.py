#! /usr/bin/python

# webcamd - A High Performance MJPEG HTTP Server
# Original author: Igor Maculan <n3wtron@gmail.com>
#
# Fixes by Christopher RYU <software-github@disavowed.jp>
# Major refactor and threading optimizations by Shell Shrader <shell@shellware.com>
#
# Bambu Printer Camera Streaming - SMS - Jan 2024
#
import os
import sys
import io
import time
import datetime
# import signal
import threading
import traceback
import socket
import argparse
import json

import struct
import ssl

from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from PIL import ImageFont, ImageDraw, Image
from io import BytesIO

exitCode = os.EX_OK
myargs = None
webserver = None
lastImage = None
encoderLock = None
encodeFps = 0.0
streamFps = {}
snapshots = 0

class WebRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global exitCode
        global myargs
        global streamFps
        global snapshots

        if self.path.lower().startswith("/?snapshot"):
            snapshots = snapshots + 1
            qs = parse_qs(urlparse(self.path).query)
            if "rotate" in qs:
                self.sendSnapshot(rotate=int(qs["rotate"][0]))
                return
            if myargs.rotate != -1:
                self.sendSnapshot(rotate=myargs.rotate)
                return
            self.sendSnapshot()
            return

        if self.path.lower().startswith("/?stream"):
            qs = parse_qs(urlparse(self.path).query)
            if "encodewait" in qs:
                myargs.encodewait = float(qs["encodewait"][0])
            showFps = myargs.showfps 
            if "showfps" in self.path.lower():
                showFps = True
            if "hidefps" in self.path.lower():
                showFps = False
            if "rotate" in qs:
                self.streamVideo(rotate=int(qs["rotate"][0]), showFps=showFps)
                return
            if myargs.rotate != -1:
                self.streamVideo(rotate=myargs.rotate, showFps=showFps)
                return
            self.streamVideo(showFps=showFps)
            return

        if self.path.lower().startswith("/?info"):
            self.send_response(200)
            self.send_header("Content-type", "text/json")
            self.end_headers()
            host = self.headers.get('Host')

            fpssum = 0.
            fpsavg = 0.

            for fps in streamFps:
                fpssum = fpssum + streamFps[fps]

            if len(streamFps) > 0:
                fpsavg = fpssum / len(streamFps)
            else:
                fpsavg = 0.

            jsonstr = ('{"stats":{"server": "%s", "encodeFps": %.2f, "sessionCount": %d, "avgStreamFps": %.2f, "sessions": %s, "snapshots": %d}, "config": %s}' % (host, self.server.getEncodeFps(), len(streamFps), fpsavg, json.dumps(streamFps) if len(streamFps) > 0 else "{}", snapshots, json.dumps(vars(myargs))))
            self.wfile.write(jsonstr.encode("utf-8"))
            return

        if self.path.lower().startswith("/?frame"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            self.wfile.write(("<html><head><title>webcamd - A High Performance MJPEG HTTP Server</title></head><body bgcolor='black'><center>" +
                             "<img width='95%' id='stream' src='/?stream' onclick=\"(function(){stream.src='/?stream&tm='+Date.now();return false;})();return false;\" " +
                             "onerror=\"(function(){setTimeout(`stream.src='/?stream&tm='+Date.now()`, 5000);return false;})();return false;\" " +
                             "onabort=\"(function(){setTimeout(`stream.src='/?stream&tm='+Date.now()`, 5000);return false;})();return false;\" " +
                             "onstalled=\"(function(){setTimeout(`stream.src='/?stream&tm='+Date.now()`, 5000);return false;})();return false;\" " +
                             "/></center></body></html>").encode("utf-8"))
            return
        
        if self.path.lower().startswith("/?shutdown"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            self.wfile.write(("<html><head><title>webcamd - A High Performance MJPEG HTTP Server</title></head><body>" +
                             "webcamd is shutting down now!</body></html>").encode("utf-8"))

            client = ("%s:%d" % (self.client_address[0], self.client_address[1]))
            print(f"{datetime.datetime.now()}: shutdown requested by {client}", flush=True)

            exitCode = os.EX_TEMPFAIL
            self.server.die()
            self.server.unlockEncoder()
            return

        self.send_response(404)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        host = self.headers.get('Host')
        self.wfile.write((
            "<html><head><title>webcamd - A High Performance MJPEG HTTP Server</title></head><body>Specify <a href='http://" + host +
            "/?frame'>/?frame</a> to host a stream in an <img> object, <a href='http://" + host +
            "/?stream'>/?stream</a> to stream, <a href='http://" + host +
            "/?snapshot'>/?snapshot</a> for a picture, or <a href='http://" + host +
            "/?info'>/?info</a> for statistics and configuration information</body></html>").encode("utf-8"))

    def log_message(self, format, *args):
        global myargs
        if not myargs.loghttp: return
        print(f"{datetime.datetime.now()}: {self.client_address[0]} {format % args}", flush=True)


    def streamVideo(self, rotate=-1, showFps = False):
        global myargs
        global streamFps

        try:
            if self.server.getImage() is None:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write((
                    "<html><head><title>webcamd - A High Performance MJPEG HTTP Server</title><meta http-equiv='refresh' content='30'>" +
                    "</head><body>Loading MJPEG Stream . . .</body></html>").encode("utf-8"))
                return
            self.send_response(200)
            self.send_header("Content-type", "multipart/x-mixed-replace; boundary=boundarydonotcross")
            self.end_headers()
        except Exception as e:
            print("%s: error in stream header %s: [%s]" % (datetime.datetime.now(), streamKey, e), flush=True)
            return

        frames = 0
        self.server.addSession()
        streamKey = ("%s:%d" % (socket.getnameinfo((self.client_address[0], 0), 0)[0], self.client_address[1]))

        fpsFont = ImageFont.truetype("SourceCodePro-Regular.ttf", 14)
        fmA, fmD = fpsFont.getmetrics()
        fmD = fmD * -1
        
        startTime = time.time()
        primed = False
        addBreaks = False

        while not self is None and not self.server is None and self.server.isRunning():
            if time.time() > startTime + 5:
                streamFps[streamKey] = frames / 5.
                # if showfps: print("%s: streaming @ %.2f FPS to %s - wait time %.5f" % (datetime.datetime.now(), streamFps[streamKey], streamKey, myargs.streamwait), flush=True)
                frames = 0
                startTime = time.time()
                primed = True

            jpg = self.server.getImage()

            if rotate != -1: jpg = jpg.rotate(rotate)

            if showFps and primed: 
                draw = ImageDraw.Draw(jpg)

                message = f"{streamKey}\n{datetime.datetime.now()}\nEncode: {round(self.server.getEncodeFps(), 1)} FPS"

                if streamKey in streamFps:
                    fpssum = 0.
                    fpsavg = 0.
                    for fps in streamFps:
                        fpssum = fpssum + streamFps[fps]
                    fpsavg = fpssum / len(streamFps)
                    message = message + f"\nStreams: {len(streamFps)} @ {round(streamFps[streamKey], 1)} FPS"

                bbox = draw.textbbox((0, fmD), message, font=fpsFont)
                draw.rectangle(bbox, fill="black")
                draw.text((0, fmD), message, font=fpsFont)

            try:
                tmpFile = BytesIO()
                jpg.save(tmpFile, format="JPEG")

                if not addBreaks:
                    self.wfile.write(b"--boundarydonotcross\r\n")
                    addBreaks = True
                else:
                    self.wfile.write(b"\r\n--boundarydonotcross\r\n")

                self.send_header("Content-type", "image/jpeg")
                self.send_header("Content-length", str(tmpFile.getbuffer().nbytes))
                self.send_header("X-Timestamp", "0.000000")
                self.end_headers()

                self.wfile.write(tmpFile.getvalue())

                time.sleep(myargs.streamwait)
                frames = frames + 1
            except Exception as e:
                # ignore broken pipes & connection reset
                if e.args[0] not in (32, 104): print(f"{datetime.datetime.now()}: error in stream {streamKey}:: [{e}]", flush=True)
                break

        if streamKey in streamFps: streamFps.pop(streamKey)
        self.server.dropSession()

    def sendSnapshot(self, rotate=-1):
        try:
            jpg = self.server.getImage()

            if jpg is None:
                self.send_error(425, "Too Early", "The server is not yet ready to serve requests.  Please try again momentarily.")
                return

            self.send_response(200)
            self.send_header("Content-type", "image/jpeg")
            self.send_header("Content-length", str(len(tmpFile.getvalue())))
            self.end_headers()

            self.server.addSession()

            if rotate != -1: jpg = jpg.rotate(rotate)
            fpsFont = ImageFont.truetype("SourceCodePro-Regular.ttf", 14)
            fmA, fmD = fpsFont.getmetrics()
            fmD = fmD * -1 

            draw = ImageDraw.Draw(jpg)

            message = f"{socket.getnameinfo((self.client_address[0], 0), 0)[0]}\n{datetime.datetime.now()}"            

            bbox = draw.textbbox((0, fmD), message, font=fpsFont)
            draw.rectangle(bbox, fill="black")
            draw.text((0, fmD), message, font=fpsFont)

            tmpFile = BytesIO()
            jpg.save(tmpFile, "JPEG")

            self.wfile.write(tmpFile.getvalue())
        except Exception as e:
            print(f"{datetime.datetime.now()}: error in snapshot: [{e}]", flush=True)

        self.server.dropSession()

def web_server_thread():
    global exitCode
    global myargs
    global webserver
    global encoderLock
    global encodeFps

    try:
        if myargs.ipv == 4:
            webserver = ThreadingHTTPServer((myargs.v4bindaddress, myargs.port), WebRequestHandler)
        else:
            webserver = ThreadingHTTPServerV6((myargs.v6bindaddress, myargs.port), WebRequestHandler)

        print(f"{datetime.datetime.now()}: web server started", flush=True)
        webserver.serve_forever()
    except Exception as e:
        exitCode = os.EX_SOFTWARE
        print(f"{datetime.datetime.now()}: web server error: [{e}]" , flush=True)

    print(f"{datetime.datetime.now()}: web server thread died", flush=True)

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    running = True
    sessions = 0

    def __init__(self, mixin, server):
        global encoderLock
        encoderLock.acquire()
        super().__init__(mixin, server)

    def getImage(self):
        global lastImage
        if not lastImage is None:
            return lastImage.copy()
        else:
            return None
        
    def die(self):
        super().shutdown()
        self.running = False
    def isRunning(self):
        return self.running
    def addSession(self):
        global encoderLock
        if self.sessions == 0 and encoderLock.locked(): encoderLock.release()
        self.sessions = self.sessions + 1
    def dropSession(self):
        global encoderLock
        global encodeFps
        global streamFps
        self.sessions = self.sessions - 1
        if self.sessions == 0 and not encoderLock.locked():
            encoderLock.acquire()
            encodeFps = 0.0
            streamFps = {}
    def unlockEncoder(self):
        global encoderLock
        if encoderLock.locked(): encoderLock.release()
    def getSessions(self):
        return self.sessions
    def getEncodeFps(self):
        global encodeFps
        return encodeFps

class ThreadingHTTPServerV6(ThreadingHTTPServer):
        address_family = socket.AF_INET6

def main():
    global exitCode
    global myargs
    global webserver
    global lastImage
    global encoderLock
    global encodeFps

    # signal.signal(signal.SIGTERM, exit_gracefully)

    # set_start_method('fork')

    parseArgs()

    encoderLock = threading.Lock()
    threading.Thread(target=web_server_thread).start()
    # Process(target=web_server_thread).start()

    # wait for our webserver to start
    while webserver is None and exitCode == os.EX_OK:
        time.sleep(.01)

    frames = 0
    startTime = time.time()

    username = 'bblp'
    access_code = myargs.password
    hostname = myargs.hostname
    port = 6000

    MAX_CONNECT_ATTEMPTS = 12
    MAX_READ_TIMEOUTS    = 10

    auth_data = bytearray()
    connect_attempts = 0
    read_timeouts = 0

    auth_data += struct.pack("<I", 0x40)   # '@'\0\0\0
    auth_data += struct.pack("<I", 0x3000) # \0'0'\0\0
    auth_data += struct.pack("<I", 0)      # \0\0\0\0
    auth_data += struct.pack("<I", 0)      # \0\0\0\0
    for i in range(0, len(username)):
        auth_data += struct.pack("<c", username[i].encode('ascii'))
    for i in range(0, 32 - len(username)):
        auth_data += struct.pack("<x")
    for i in range(0, len(access_code)):
        auth_data += struct.pack("<c", access_code[i].encode('ascii'))
    for i in range(0, 32 - len(access_code)):
        auth_data += struct.pack("<x")

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    jpeg_start = bytearray([0xff, 0xd8, 0xff, 0xe0])
    jpeg_end = bytearray([0xff, 0xd9])

    read_chunk_size = 4096 # 4096 is the max we'll get even if we increase this.

    # Payload format for each image is:
    # 16 byte header:
    #   Bytes 0:3   = little endian payload size for the jpeg image (does not include this header).
    #   Bytes 4:7   = 0x00000000
    #   Bytes 8:11  = 0x00000001
    #   Bytes 12:15 = 0x00000000
    # These first 16 bytes are always delivered by themselves.
    #
    # Bytes 16:19                       = jpeg_start magic bytes
    # Bytes 20:payload_size-2           = jpeg image bytes
    # Bytes payload_size-2:payload_size = jpeg_end magic bytes
    #
    # Further attempts to receive data will get SSLWantReadError until a new image is ready (1-2 seconds later)
    while connect_attempts < MAX_CONNECT_ATTEMPTS and not webserver is None and webserver.isRunning():
        try:
            with socket.create_connection((hostname, port)) as sock:
                connect_attempts += 1
                sslSock = ctx.wrap_socket(sock, server_hostname=hostname)
                sslSock.write(auth_data)
                img = None
                payload_size = 0

                status = sslSock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if status != 0:
                    raise Exception(f"Socket error: {status}")

                # sslSock.setblocking(False)
                sslSock.settimeout(10.0)

                while not webserver is None and webserver.isRunning() and read_timeouts < MAX_READ_TIMEOUTS:
                    if  time.time() > startTime + 5:
                        encodeFps = frames / 5.
                        if encodeFps <= 0: encodeFps = 1
                        myargs.streamwait = 1 / encodeFps
                        # if myargs.showfps: print("%s: encoding @ %.2f FPS - wait time %.5f" % (datetime.datetime.now(), encodeFps, myargs.encodewait), flush=True)
                        frames = 0
                        startTime = time.time()
                        # dr = 0

                    try:
                        dr = sslSock.recv(read_chunk_size)
                    except TimeoutError as e:
                        time.sleep(1)
                        print(f"{datetime.datetime.now()}: socket read timeout", flush=True)
                        read_timeouts = read_timeouts + 1
                        continue

                    if img is not None and len(dr) > 0:
                        img += dr
                        if len(img) > payload_size:
                            print(f"{datetime.datetime.now()}: We got more data than we expected", flush=True)
                            img = None
                        elif len(img) == payload_size:
                            # We should have the full image now.
                            if img[:4] != jpeg_start:
                                print(f"{datetime.datetime.now()}: JPEG start magic bytes missing", flush=True)
                            elif img[-2:] != jpeg_end:
                                print(f"{datetime.datetime.now()}: JPEG end magic bytes missing", flush=True)
                            else:
                                read_timeouts = 0
                                lastImage = Image.open(io.BytesIO(img)).convert('RGB')
                                frames = frames + 1.0
                                if encoderLock.locked():
                                    encoderLock.acquire()
                                    encoderLock.release()
                            # Reset buffer
                            img = None
                            time.sleep(myargs.encodewait)
                        # else:     
                        # Otherwise we need to continue looping without reseting the buffer to receive the remaining data
                        # and without delaying.

                    elif len(dr) == 16:
                        # We got the header bytes. Get the expected payload size from it and create the image buffer bytearray.
                        # Reset connect_attempts now we know the connect was successful.
                        connect_attempts = 0
                        img = bytearray()
                        payload_size = int.from_bytes(dr[0:3], byteorder='little')

                    elif len(dr) == 0:
                        # This occurs if the wrong access code was provided.
                        # LOGGER.error(f"{self._client._device.info.device_type}: Chamber image connection rejected by the printer. Check provided access code and IP address.")
                        # Sleep for a short while and then re-attempt the connection.
                        time.sleep(1)
                        print(f"{datetime.datetime.now()}: no data received - possible invalid access code provided", flush=True)
                        read_timeouts = read_timeouts + 1
                        continue

                    else:
                        # print("unexpected error")
                        # time.sleep(1)
                        # raise Exception("unknown error occurred")
                        print(f"{datetime.datetime.now()}: unknown error occurred", flush=True)

        # except KeyboardInterrupt:
        #     print(f"{datetime.datetime.now()}: shutdown requested", flush=True)
        #     sslSock.shutdown(socket.SHUT_RDWR)
        #     break

        except ConnectionResetError:
            print(f"{datetime.datetime.now()}: Connection Reset", flush=True)
            
        except Exception as e:
            print(f"{datetime.datetime.now()}: {traceback.format_exc()}", flush=True)
            exitCode = os.EX_TEMPFAIL
            break

    if not webserver is None and webserver.isRunning():
        print(f"{datetime.datetime.now()}: web server shutting down", flush=True)
        webserver.die()

    time.sleep(1)

    print(f"{datetime.datetime.now()}: ExitCode={exitCode} - Goodbye!", flush=True)
    sys.exit(exitCode)


def parseArgs():
    global myargs

    parser = argparse.ArgumentParser(
        description="webcam.py - A High Performance MJPEG HTTP Server"
    )
    parser.add_argument(
        "--hostname",
        type=str,
        required=True,
        help="Bambu Printer IP address / hostname"
    )
    parser.add_argument(
        "--password",
        type=str,
        required=True,
        help="Bambu Printer Access Code"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1920,
        help="web camera pixel width (default 1920)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=1080,
        help="web camera pixel height (default 1080)",
    )

    parser.add_argument("--ipv", type=int, default=4, help="IP version (default=4)")

    parser.add_argument(
        "--v4bindaddress",
        type=str,
        default="0.0.0.0",
        help="IPv4 HTTP bind address (default '0.0.0.0')",
    )
    parser.add_argument(
        "--v6bindaddress",
        type=str,
        default="::",
        help="IPv6 HTTP bind address (default '::')",
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="HTTP bind port (default 8080)"
    )
    parser.add_argument(
        "--encodewait", type=float, default=.5, help="seconds to pause between capturing encoded frames (default .5)"
    )
    parser.add_argument(
        "--streamwait", type=float, default=.01, help="not used - is set dynamically based on measured encoding fps"
    )
    parser.add_argument(
        "--rotate", type=int, default=-1, help="rotate captured image 1-359 in degrees - (default no rotation)"
    )
    parser.add_argument('--showfps', action='store_true', help="periodically show encoding / streaming frame rate (default false)")
    parser.add_argument('--loghttp', action='store_true', help="enable http server logging (default false)")

    myargs = parser.parse_args()

# def exit_gracefully(signum, frame):
#     global webserver

#     if not webserver is None and webserver.isRunning():
#         print(f"{datetime.datetime.now()}: web server shutting down", flush=True)
#         webserver.shutdown()

#     raise KeyboardInterrupt()

if __name__ == "__main__":
    main()
