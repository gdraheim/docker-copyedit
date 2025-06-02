FROM alpine as docker
# adds runc, containerd which are overkill for docker-cli
RUN apk add --no-cache docker

FROM python:3-alpine
ENTRYPOINT ["docker_copyedit.py"]
RUN apk add --no-cache libltdl
COPY --from=docker /usr/bin/docker /usr/bin/docker
COPY docker_copyedit1/docker_copyedit*.py /usr/local/bin/
