FROM ubuntu:14.04
MAINTAINER Petr Lomakin <plomakin@mirantis.com>

ARG cf_commit_or_branch

RUN apt-get update --fix-missing
RUN apt-get install vim git nfs-common python-software-properties build-essential libssl-dev libffi-dev python-dev sqlite wget -y

RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python get-pip.py
RUN pip install virtualenv

RUN git clone https://github.com/MirantisWorkloadMobility/CloudFerry CloudFerry
WORKDIR /CloudFerry
RUN git checkout $cf_commit_or_branch

RUN pip install .
