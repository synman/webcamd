#! /usr/bin/python

# A simple MJPEG HTTP server for Octoprint
# Original author: Igor Maculan <n3wtron@gmail.com>
#
# Fixes by Christopher RYU <software-github@disavowed.jp>

import cv2
from PIL import Image
import threading
from http.server import BaseHTTPRequestHandler,HTTPServer
from socketserver import ThreadingMixIn
from io import StringIO
from io import BytesIO
import time
import sys
import socket
import argparse

capture=None

class CamHandler(BaseHTTPRequestHandler):
  def do_GET(self):
    if self.path == '/?snapshot':
      self.sendSnapshot()
    else:
      self.streamVideo()

  def streamVideo(self):
    self.send_response(200)
    self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=--jpgboundary')
    self.end_headers()
    while True:
      try:
        rc,img = capture.read()
        if not rc:
          continue
        jpg = Image.fromarray(img)
        tmpFile = BytesIO()
        jpg.save(tmpFile, "JPEG")
        self.wfile.write( b'--jpgboundary\n')
        self.send_header('Content-type', 'image/jpeg')
        self.send_header('Content-length', str(sys.getsizeof(tmpFile)))
        self.end_headers()
        self.wfile.write( tmpFile.getvalue() )
        time.sleep(0.05)
      except:
        break

  def sendSnapshot(self):
    self.send_response(200)
    try:
      rc,img = capture.read()
      if not rc:
        return
      jpg = Image.fromarray(img)
      tmpFile = BytesIO()
      jpg.save(tmpFile, "JPEG")
      self.send_header('Content-type', 'image/jpeg')
      self.send_header('Content-length', str( len(tmpFile.getvalue()) ))
      self.end_headers()
      self.wfile.write( tmpFile.getvalue() )
    except:
      pass
 
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
  """Handle requests in a separate thread."""

class ThreadedHTTPServerV6(ThreadedHTTPServer):
  address_family = socket.AF_INET6

def main():
  global capture

  parser = argparse.ArgumentParser(description='A simple MJPEG HTTP server for Octoprint')
  parser.add_argument('--width', type=int, default=1920, help='Web camera pixel width (default 1920)')
  parser.add_argument('--height', type=int, default=1080, help='Web camera pixel height (default 1080)')
  parser.add_argument('--index', type=int, default=0, help='/dev/videoX (default X=0)')
  parser.add_argument('--v4bindaddress', type=str, default='0.0.0.0', help='IPv4 HTTP bind address (default \'0.0.0.0\')')
  parser.add_argument('--v6bindaddress', type=str, default='::', help='IPv6 HTTP bind address (default \'::\')')
  parser.add_argument('--port', type=int, default=8080, help='HTTP bind port (default 8080)')
  parser.add_argument('--ipv', type=int, default=6, help='IP version (default=6)')

  args = parser.parse_args()

  capture = cv2.VideoCapture(args.index)
  capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width); 
  capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height);
  try:
    if args.ipv == 4:
      server = ThreadedHTTPServer((args.v4bindaddress, args.port), CamHandler)
    else:
      server = ThreadedHTTPServerV6((args.v6bindaddress, args.port), CamHandler)
    print("server started")
    server.serve_forever()
  except:
    capture.release()
    server.socket.close()

if __name__ == '__main__':
  main()
