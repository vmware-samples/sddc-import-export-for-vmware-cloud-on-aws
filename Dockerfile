# Written by clennon
FROM bitnami/python:3.9.5-prod

WORKDIR /tmp/scripts

COPY requirements.txt ./
RUN apt-get -y update
RUN apt-get -y install git
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir -r requirements.txt
RUN git clone https://github.com/vmware-samples/sddc-import-export-for-vmware-cloud-on-aws.git