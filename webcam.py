#! /usr/bin/python

# webcamd - A High Performance MJPEG HTTP Server
# Original author: Igor Maculan <n3wtron@gmail.com>
#
# Fixes by Christopher RYU <software-github@disavowed.jp>
# Major refactor and threading optimizations by Shell Shrader <shell@shellware.com>

import os
import sys
import time
import datetime
import signal
import threading
import socket
import cv2
import argparse
import json

from picamera2 import Picamera2
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
encodeFps = 0.
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
            if "rotate" in qs:
                self.streamVideo(rotate=int(qs["rotate"][0]))
                return
            if myargs.rotate != -1:
                self.streamVideo(rotate=myargs.rotate)
                return
            self.streamVideo()
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

        if self.path.lower().startswith("/?shutdown"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()

            client = ("%s:%d" % (self.client_address[0], self.client_address[1]))
            print("%s: shutdown requested by %s" % (datetime.datetime.now(), client), flush=True)

            exitCode = os.EX_TEMPFAIL
            self.server.shutdown()
            self.server.unlockEncoder()
            return

        self.send_response(404)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        host = self.headers.get('Host')
        self.wfile.write((
            "<html><head><title>webcamd - A High Performance MJPEG HTTP Server</title></head><body>Specify <a href='http://" + host +
            "/?stream'>/?stream</a> to stream, <a href='http://" + host +
            "/?snapshot'>/?snapshot</a> for a picture, or <a href='http://" + host +
            "/?info'>/?info</a> for statistics and configuration information</body></html>").encode("utf-8"))

    def log_message(self, format, *args):
        global myargs
        if not myargs.loghttp: return
        print(("%s: " % datetime.datetime.now()) + (format % args), flush=True)


    def streamVideo(self, rotate=-1, showFps = False):
        global myargs
        global streamFps

        frames = 0
        self.server.addSession()
        streamKey = ("%s:%d" % (socket.getnameinfo((self.client_address[0], 0), 0)[0], self.client_address[1]))

        try:
            self.send_response(200)
            self.send_header(
                "Content-type", "multipart/x-mixed-replace; boundary=boundarydonotcross"
            )
            self.end_headers()
        except Exception as e:
            print("%s: error in stream header %s: [%s]" % (datetime.datetime.now(), streamKey, e), flush=True)
            return

        fpsFont = ImageFont.truetype(f"{os.path.dirname(os.path.abspath(sys.argv[0]))}/SourceCodePro-Regular.ttf", 20)
        #fpsW, fpsH = fpsFont.getsize("A")
        ignore,ignore,fpsW, fpsH = fpsFont.getbbox("A")
        startTime = time.time()
        primed = True
        addBreaks = False

        while self.server.isRunning():
            if time.time() > startTime + 5:
                streamFps[streamKey] = frames / 5.
                # if myargs.showfps: print("%s: streaming @ %.2f FPS to %s - wait time %.5f" % (datetime.datetime.now(), streamFps[streamKey], streamKey, myargs.streamwait), flush=True)
                frames = 0
                startTime = time.time()
                primed = True

            jpg = self.server.getImage()
            if rotate != -1: jpg = jpg.rotate(rotate)

            if myargs.showfps and primed: 
                draw = ImageDraw.Draw(jpg)
                draw.text((0, 0), "%s" % streamKey, font=fpsFont)
                draw.text((0, fpsH + 1), "%s" % datetime.datetime.now(), font=fpsFont)
                draw.text((0, fpsH * 2 + 2), "Encode: %.0f FPS" % self.server.getEncodeFps(), font=fpsFont)
                if streamKey in streamFps: 
                    fpssum = 0.
                    fpsavg = 0.
                    for fps in streamFps:
                        fpssum = fpssum + streamFps[fps]
                    fpsavg = fpssum / len(streamFps)
                    draw.text((0, fpsH * 3 + 3), "Streams: %d @ %.1f FPS (avg)" % (len(streamFps), streamFps[streamKey]), font=fpsFont)

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
                if e.args[0] not in (32, 104): print("%s: error in stream %s: [%s]" % (datetime.datetime.now(), streamKey, e), flush=True)
                break

        if streamKey in streamFps: streamFps.pop(streamKey)
        self.server.dropSession()


    def sendSnapshot(self, rotate=-1):
        global lastImage

        self.server.addSession()

        try:
            self.send_response(200)

            jpg = self.server.getImage()
            if rotate != -1: jpg = jpg.rotate(rotate)

            fpsFont = ImageFont.truetype(f"{os.path.dirname(os.path.abspath(sys.argv[0]))}/SourceCodePro-Regular.ttf", 20)
            #fpsW, fpsH = fpsFont.getsize("A")
            ignore,ignore,fpsW, fpsH = fpsFont.getbbox("A")
            draw = ImageDraw.Draw(jpg)

            draw.text((0, 0), "%s" % socket.getnameinfo((self.client_address[0], 0), 0)[0], font=fpsFont)
            draw.text((0, fpsH + 1), "%s" % datetime.datetime.now(), font=fpsFont)

            tmpFile = BytesIO()
            jpg.save(tmpFile, "JPEG")

            self.send_header("Content-type", "image/jpeg")
            self.send_header("Content-length", str(len(tmpFile.getvalue())))
            self.end_headers()

            self.wfile.write(tmpFile.getvalue())
        except Exception as e:
            print("%s: error in snapshot: [%s]" % (datetime.datetime.now(), e), flush=True)

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

        print("%s: web server started" % datetime.datetime.now(), flush=True)
        webserver.serve_forever()
    except Exception as e:
        exitCode = os.EX_SOFTWARE
        print("%s: web server error: [%s]" % (datetime.datetime.now(), e), flush=True)

    print("%s: web server thread dead" % (datetime.datetime.now()), flush=True)

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    running = True
    sessions = 0

    def __init__(self, mixin, server):
        global encoderLock
        encoderLock.acquire()
        super().__init__(mixin, server)

    def getImage(self):
        global lastImage
        return lastImage
    def shutdown(self):
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
            encodeFps = 0.
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

    signal.signal(signal.SIGTERM, exit_gracefully)

    # set_start_method('fork')

    parseArgs()

    encoderLock = threading.Lock()
    threading.Thread(target=web_server_thread).start()
    # Process(target=web_server_thread).start()

    # wait for our webserver to start
    while webserver is None and exitCode == os.EX_OK:
        time.sleep(.01)

    # initialize our opencv encoder
    #capture = cv2.VideoCapture(myargs.index)
    #capture.set(cv2.CAP_PROP_FRAME_WIDTH, myargs.width)
    #capture.set(cv2.CAP_PROP_FRAME_HEIGHT, myargs.height)

    # Initialize Picamera2
    picam2 = Picamera2()
    preview_config = picam2.create_preview_configuration(main={"size": (myargs.width, myargs.height), "format": "RGB888"})
    picam2.configure(preview_config)

    picam2.start()
    time.sleep(1)

    frames = 0
    startTime = time.time()

    while webserver.isRunning():
        if  time.time() > startTime + 5:
            encodeFps = frames / 5.
            # myargs.streamwait =  1. / encodeFps 
            # if myargs.showfps: print("%s: encoding @ %.2f FPS - wait time %.5f" % (datetime.datetime.now(), encodeFps, myargs.encodewait), flush=True)
            frames = 0
            startTime = time.time()
        try:
            #rc, img_bgr = capture.read()
            #img_bgr = picam2.capture_array()
            job = picam2.capture_array(wait=False)
            img_bgr = job.get_result(timeout=1.0) 
            lastImage = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))

            time.sleep(myargs.encodewait)
            frames = frames + 1.0

            if encoderLock.locked():
                encoderLock.acquire()
                encoderLock.release()

        except KeyboardInterrupt:
            break
        except Exception as e:
            exitCode = os.EX_SOFTWARE
            print("%s: error in capture: [%s]" % (datetime.datetime.now(), e), flush=True)
            break

    if not webserver is None and webserver.isRunning():
        print("%s: web server shutting down" % (datetime.datetime.now()), flush=True)
        webserver.shutdown()

    print("%s: ExitCode=%d - Goodbye!" % (datetime.datetime.now(), exitCode), flush=True)
    sys.exit(exitCode)


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
        "--encodewait", type=float, default=.01, help="seconds to pause between encoding frames (default .01)"
    )
    parser.add_argument(
        "--streamwait", type=float, default=.01, help="seconds to pause between streaming frames (default .01)"
    )
    parser.add_argument(
        "--rotate", type=int, default=-1, help="rotate captured image 1-359 in degrees - (default no rotation)"
    )
    parser.add_argument('--showfps', action='store_true', help="periodically show encoding / streaming frame rate (default false)")
    parser.add_argument('--loghttp', action='store_true', help="enable http server logging (default false)")

    myargs = parser.parse_args()

def exit_gracefully(signum, frame):
    raise KeyboardInterrupt()

if __name__ == "__main__":
    main()
