FROM ubuntu:14.04
MAINTAINER Petr Lomakin <plomakin@mirantis.com>

ARG cf_commit_or_branch

RUN apt-get update --fix-missing

RUN apt-get install vim git nfs-common python-virtualenv python-software-properties -y

RUN apt-get install build-essential libssl-dev libffi-dev python-dev python-pip -y

RUN pip install pip==7.1.2

RUN git clone https://github.com/MirantisWorkloadMobility/CloudFerry CloudFerry

WORKDIR /CloudFerry

RUN git checkout $cf_commit_or_branch

RUN pip install -r requirements.txt -r test-requirements.txt
