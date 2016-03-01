============
Installation
============

Currently there are two possible ways of installing CloudFerry:

 - In docker container
 - In python virtual environment

docker
------
::

    git clone https://github.com/MirantisWorkloadMobility/CloudFerry.git
    cd CloudFerry
    docker build --build-arg cf_commit_or_branch=origin/master -t <username>/cf-in-docker .
    docker run -it <username>/cf-in-docker

python virtual environment
--------------------------

::

    git clone https://github.com/MirantisWorkloadMobility/CloudFerry.git
    cd CloudFerry
    virtualenv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

