FROM ubuntu:14.04
MAINTAINER Petr Lomakin <plomakin@mirantis.com>

ARG cf_commit_or_branch

RUN apt-get update --fix-missing
RUN apt-get install -y \
    git \
    nfs-common \
    build-essential \
    libssl-dev \
    libffi-dev \
    python-dev \
    sqlite \
    wget

RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python get-pip.py
RUN pip install virtualenv==15.0.3

RUN git clone https://github.com/MirantisWorkloadMobility/CloudFerry CloudFerry
WORKDIR /CloudFerry
RUN git checkout $cf_commit_or_branch

RUN pip install .
