FROM python:3-slim

EXPOSE 8080

WORKDIR /usr/src/app

RUN pip install --no-cache-dir pillow

COPY webcam.py ./
COPY SourceCodePro-Regular.ttf ./

ENV HOSTNAME=localhost
ENV ACCESS_CODE=111111
ENV WIDTH=1920
ENV HEIGHT=1080
ENV ENCODEWAIT=0.5
ENV ROTATE=-1

ENTRYPOINT python ./webcam.py --hostname $HOSTNAME --password $ACCESS_CODE --width $WIDTH --height $HEIGHT --port 8080 --encodewait $ENCODEWAIT --rotate $ROTATE --loghttp

