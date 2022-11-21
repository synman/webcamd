#! /usr/bin/python

# webcamd - A High Performance MJPEG HTTP Server
# Original author: Igor Maculan <n3wtron@gmail.com>
#
# Fixes by Christopher RYU <software-github@disavowed.jp>
# Major refactor and threading optimizations by Shell Shrader <shell@shellware.com>

import cv2
import threading
import time
import sys
import socket
import argparse
import datetime

from PIL import Image
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from io import StringIO
from io import BytesIO

lock = None
lastImage = None
myargs = None

class WebRequest(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/?snapshot":
            self.sendSnapshot()
        else:
            if self.path == "/?stream":
                self.streamVideo()
            else:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                host = self.headers.get('Host')
                self.wfile.write(
                    ("<html><head><title>webcamd</title></head><body>Specify <a href='http://" + host + "/?stream'>/?stream</a> to stream or <a href='http://" + host + "/?snapshot'>/?snapshot</a> for a picture</body></html>").encode(
                        "utf-8"
                    )
                )

    def log_message(self, format, *args):
        global myargs
        if not myargs.loghttp: return
        print(("%s: " % datetime.datetime.now()) + (format % args))

    def streamVideo(self):
        global myargs
        global lastImage

        frames = 0
        startTime = time.time()

        try:
            self.send_response(200)
            self.send_header(
                "Content-type", "multipart/x-mixed-replace; boundary=--jpgboundary"
            )
            self.end_headers()
        except Exception as e:
            print("%s: error in stream: [%s]" % (datetime.datetime.now(), e))
            return

        while True:
            if myargs.showfps and time.time() > startTime + 5:
                print("%s: streaming @ %.2f FPS to %s - wait time %.5f" % (datetime.datetime.now(), frames / 5., self.client_address[0], myargs.streamwait))
                frames = 0
                startTime = time.time()

            lock.acquire()
            jpg = Image.fromarray(lastImage)
            lock.release()

            try:
                tmpFile = BytesIO()
                jpg.save(tmpFile, "JPEG")

                self.wfile.write(b"--jpgboundary\n")
                self.send_header("Content-type", "image/jpeg")
                self.send_header("Content-length", str(sys.getsizeof(tmpFile)))
                self.end_headers()
                self.wfile.write(tmpFile.getvalue())

                time.sleep(myargs.streamwait)
                frames = frames + 1
            except Exception as e:
                # ignore broken pipes
                if e.args[0] != 32: print("%s: error in stream: [%s]" % (datetime.datetime.now(), e))
                return

    def sendSnapshot(self):
        global lastImage

        lock.acquire()
        jpg = Image.fromarray(lastImage)
        lock.release()

        try:
            self.send_response(200)

            tmpFile = BytesIO()
            jpg.save(tmpFile, "JPEG")

            self.send_header("Content-type", "image/jpeg")
            self.send_header("Content-length", str(len(tmpFile.getvalue())))
            self.end_headers()
            self.wfile.write(tmpFile.getvalue())
        except Exception as e:
            print("%s: error in snapshot: [%s]" % (datetime.datetime.now(), e))

def web_server_thread():
    global myargs
    server = None

    try:
        server = ThreadedHTTPServer((myargs.v4bindaddress if myargs.ipv == 4 else myargs.v6bindaddress, myargs.port), WebRequest)

        print("%s: web server started" % datetime.datetime.now())
        server.serve_forever()
    except Exception as e:
        print("%s: web server error: [%s]" % (datetime.datetime.now(), e))
        if not server is None: server.socket.close()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

class ThreadedHTTPServerV6(ThreadedHTTPServer):
    address_family = socket.AF_INET6

def main():
    global lock
    global lastImage
    global myargs

    lock = threading.Lock()

    parseArgs()

    threading.Thread(target=web_server_thread).start()

    capture = cv2.VideoCapture(myargs.index)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, myargs.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, myargs.height)

    frames = 0
    startTime = time.time()

    while True:
        if myargs.showfps and time.time() > startTime + 5:
            print("%s: encoding @ %.2f FPS - wait time %.5f" % (datetime.datetime.now(), frames / 5., myargs.encodewait))
            frames = 0
            startTime = time.time()
        try:
            rc, img_bgr = capture.read()
            if not rc:
                print("%s: restarting encoder due to timeouts" % datetime.datetime.now())
                capture.release()
                capture = cv2.VideoCapture(myargs.index)
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, myargs.width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, myargs.height)
                continue

            img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            if myargs.rotate != -1: img = cv2.rotate(img, myargs.rotate)

            lock.acquire()
            lastImage = img.copy()
            lock.release()

            time.sleep(myargs.encodewait)
            frames = frames + 1.0
        except Exception as e:
            print("%s: error in capture: [%s]" % (datetime.datetime.now(), e))
            if lock.locked(): lock.release()

def parseArgs():
    global myargs

    parser = argparse.ArgumentParser(
        description="webcam.py - A High Performance MJPEG HTTP Server"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Web camera pixel width (default 1280)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=720,
        help="Web camera pixel height (default 720)",
    )
    parser.add_argument(
        "--index", type=int, default=0, help="Video device to stream /dev/video# (default #=0)"
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
        "--encodewait", type=float, default=.001, help="seconds to pause between encoding frames (default .001)"
    )
    parser.add_argument(
        "--streamwait", type=float, default=.01, help="seconds to pause between streaming frames (default .01)"
    )
    parser.add_argument(
        "--rotate", type=int, default=-1, help="rotate captured image 0=90+, 1=180, 2=90- (default no rotation)"
    )
    parser.add_argument('--showfps', action='store_true', help="periodically show encoding / streaming frame rate (default false)")
    parser.add_argument('--loghttp', action='store_true', help="enable http server logging (default false)")

    myargs = parser.parse_args()

if __name__ == "__main__":
    main()
