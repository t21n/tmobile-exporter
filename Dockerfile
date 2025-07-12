FROM python:3.12.4-alpine

ARG BUILD_DATE
ARG APP_VERSION

LABEL org.opencontainers.image.authors='Martin Reinhardt (martin@m13t.de)' \
    org.opencontainers.image.created=$BUILD_DATE \
    org.opencontainers.image.version=$APP_VERSION \
    org.opencontainers.image.url='https://hub.docker.com/r/tools4homeautomation/tmobile-exporter' \
    org.opencontainers.image.documentation='https://github.com/t21n/tmobile-exporter' \
    org.opencontainers.image.source='https://github.com/t21n/tmobile-exporter.git' \
    org.opencontainers.image.licenses='MIT'

COPY app .
RUN pip3 install -r requirements.txt

CMD python3 main.py