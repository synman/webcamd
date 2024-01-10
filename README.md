# webcamd - A High Performance (for python) MPJEG HTTP Server

## <B>Now supports Bambu printers</B>

The most notable component is webcam.py.  It is a minimalist drop-in replacement
for mjpg-streamer, written in python.  It can also be completely decoupled from OctoPrint and used in your own custom environment.

webcam.py is based on Igor Maculan’s “Simple Python Motion Jpeg” daemon (https://gist.github.com/n3wtron/4624820).  It has been reworked to run under python-3.x, accept command-line tunables, IPv6 support, and so forth.

webcam@.service is a systemd unit file for webcam.py.

haproxy.cfg is a configuration file for haproxy that actually works with non-ancient versions of haproxy, and enforces SSL connections to Octoprint.

In addition to Christopher RYU's <software-github@disavowed.jp> baseline additions, this version of webcamd has been significanly reworked to run as a multi-threaded MJPEG encoder (using opencv and pillow), and Python's multi-threaded HTTP server.

Bambu Printer support is based on proof of concept work found in bambulab/BambuStudio#1536 (comment) that were later optimized in [pybambu](https://github.com/greghesp/pybambu).

## Dependencies
```
pip install pillow
```
## Command Line Options
```
webcam.py - A High Performance MJPEG HTTP Server

options:
  -h, --help            show this help message and exit
  --hostname HOSTNAME   Bambu Printer IP address / hostname
  --password PASSWORD   Bambu Printer Access Code
  --width WIDTH         Web camera pixel width (default 1920)
  --height HEIGHT       Web camera pixel height (default 1080)
  --ipv IPV             IP version (default=4)
  --v4bindaddress V4BINDADDRESS
                        IPv4 HTTP bind address (default '0.0.0.0')
  --v6bindaddress V6BINDADDRESS
                        IPv6 HTTP bind address (default '::')
  --port PORT           HTTP bind port (default 8080)
  --encodewait ENCODEWAIT
                        not used
  --streamwait STREAMWAIT
                        not used - is set dynamically
  --rotate ROTATE       rotate captured image 1-359 in degrees - (default no rotation)
  --showfps             periodically show encoding / streaming frame rate (default false)
  --loghttp             enable http server logging (default false)
```
## Useful Information
Specify `/?stream` to stream, `/?snapshot` for a picture, or `/?info` for statistics and configuration information.

You can rotate the encoded image for all clients using the `--rotate` command line option (adds overhead at the encoder) and/or you can also specify on a per stream basis with the `&rotate=` querystring option (`/?stream&rotate=#` or `/?snapshot&rotate=#`) which offloads the rotation to the client session thread.
 
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

### Note:
--showfps has been modified to embed a watermark on mjpeg streams and snapshots.  This, along with rotation, greatly impacts encoding and stream performance, but it is nice addition if you're okay with a +/- 10 FPS framerate when running on a SoC such as the pi zero2.

<img width="289" alt="Screenshot 2022-12-28 at 1 35 02 PM" src="https://user-images.githubusercontent.com/1299716/209857494-437c9464-8ebf-44f8-8785-04df0a82a31a.png">

