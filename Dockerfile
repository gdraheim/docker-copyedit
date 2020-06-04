FROM alpine as docker
# adds runc, containerd which are overkill for docker-cli
RUN apk add --no-cache docker

FROM python:2-alpine
ENTRYPOINT ["docker-copyedit.py"]
RUN apk add --no-cache libltdl
COPY --from=docker /usr/bin/docker /usr/bin/docker
COPY docker-copyedit*.py /usr/local/bin/
