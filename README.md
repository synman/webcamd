# webcamd - A High Performance (for python) MPJEG HTTP Server

The most notable component is webcam.py.  It is a minimalist drop-in replacement
for mjpg-streamer, written in python, that addresses the following issues:

* Octoprint appends a seemingly-random session ID to the camera URI, which confuses the hell out of mjpg-streamer,
* mjpg-streamer doesn’t appear to handle multiple simultaneous streams, resulting in the infuriating “403: Forbidden! frame already sent” error,
* mjpg-streamer itself is complete overkill here.

webcam.py is based on Igor Maculan’s “Simple Python Motion Jpeg” daemon (https://gist.github.com/n3wtron/4624820).  It has been reworked to run under python-3.x, accept command-line tunables, IPv6 support, and so forth.

Please note that the webcam.py process needs read/write access to the video device (typically /dev/video0).  Adding the user that webcam.py runs as to the "video" group will usually suffice.

webcam@.service is a systemd unit file for webcam.py.

haproxy.cfg is a configuration file for haproxy that actually works with non-ancient versions of haproxy, and enforces SSL connections to Octoprint.

In addition to Christopher RYU's <software-github@disavowed.jp> baseline additions, this version of webcamd has been significanly reworked to run as a multi-threaded MJPEG encoder (using opencv), and Python's multi-threaded HTTP server.

## Dependencies
```
pip install opencv-python
pip install pillow
```
## Command Line Options
```
webcam.py - A High Performance MJPEG HTTP Server

optional arguments:
  -h, --help            show this help message and exit
  --width WIDTH         Web camera pixel width (default 1280)
  --height HEIGHT       Web camera pixel height (default 720)
  --index INDEX         Video device to stream /dev/video# (default #=0)
  --ipv IPV             IP version (default=4)
  --v4bindaddress V4BINDADDRESS
                        IPv4 HTTP bind address (default '0.0.0.0')
  --v6bindaddress V6BINDADDRESS
                        IPv6 HTTP bind address (default '::')
  --port PORT           HTTP bind port (default 8080)
  --encodewait ENCODEWAIT
                        seconds to pause between encoding frames (default .01)
  --streamwait STREAMWAIT
                        seconds to pause between streaming frames (default .01)
  --rotate ROTATE       rotate captured image 0=90+, 1=180, 2=90- (default no rotation)
  --showfps             periodically show encoding / streaming frame rate (default false)
  --loghttp             enable http server logging (default false)
```
## Useful Information
Specify `/?stream` to stream, `/?snapshot` for a picture, or `/?info` for statistics and configuration information.

You can rotate the encoded image for all clients using the `--rotate` command line option (adds overhead at the encoder) and/or you can also specify on a per stream basis with the `&rotate=` querystring option, ie:  /?stream&rotate=1, which offloads the rotation to the client session thread.

`--encodewait` and `--streamwait` can be used to rebalance the priority of encoding vs streaming.  

`/?info` produces a json document that shows various information about the state of the encoder and active streams, as well as the active configuration.
```
{
  stats: {
    server: "qbp-webcam:8080",
    encodeFps: 19,
    sessionCount: 1,
    avgStreamFps: 18.4,
    sessions: {
      10.151.51.244:41578: 18.4
    },
    snapshots: 0
  },
  config: {
    width: 1280,
    height: 720,
    index: 0,
    ipv: 4,
    v4bindaddress: "0.0.0.0",
    v6bindaddress: "::",
    port: 8080,
    encodewait: 0.01,
    streamwait: 0.01,
    rotate: -1,
    showfps: false,
    loghttp: false
  }
}
```
Statistics and `--showfps` logging update every 5 seconds.
