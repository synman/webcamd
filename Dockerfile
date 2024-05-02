FROM python:3.9-slim

WORKDIR /app

# Klonen des neuesten Codes aus dem GitHub Repository
RUN apt-get update \
    && apt-get install -y git libjpeg-dev zlib1g-dev gcc \
    && git clone -b bambu https://github.com/synman/webcamd.git /app \
    && apt-get purge -y --auto-remove git \
    && rm -rf /var/lib/apt/lists/*

# Installieren der benötigten Python-Bibliothek
RUN pip install --upgrade pip
RUN pip install pillow

# Expose the default port for the HTTP server
EXPOSE 8080

# Verwendung eines Inline-Shell-Skripts zur kontrollierten Übergabe von Umgebungsvariablen
CMD exec python webcam.py \
    --hostname "${HOSTNAME:-localhost}" \
    $( [ -n "${PASSWORD}" ] && echo "--password ${PASSWORD}" ) \
    $( [ -n "${WIDTH}" ] && echo "--width ${WIDTH}" ) \
    $( [ -n "${HEIGHT}" ] && echo "--height ${HEIGHT}" ) \
    $( [ -n "${IPV}" ] && echo "--ipv ${IPV}" ) \
    $( [ -n "${V4BINDADDRESS}" ] && echo "--v4bindaddress ${V4BINDADDRESS}" ) \
    $( [ -n "${V6BINDADDRESS}" ] && echo "--v6bindaddress ${V6BINDADDRESS}" ) \
    $( [ -n "${PORT}" ] && echo "--port ${PORT}" ) \
    $( [ -n "${ENCODEWAIT}" ] && echo "--encodewait ${ENCODEWAIT}" ) \
    $( [ -n "${STREAMWAIT}" ] && echo "--streamwait ${STREAMWAIT}" ) \
    $( [ -n "${ROTATE}" ] && echo "--rotate ${ROTATE}" ) \
    $( [ -n "${SHOWFPS}" ] && echo "--showfps" ) \
    $( [ -n "${LOGHTTP}" ] && echo "--loghttp" )