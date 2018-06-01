FROM wholetale/girder:stable

RUN apt-get update -qqy && \
  DEBIAN_FRONTEND=noninteractive apt-get -qy install \
    build-essential \
    vim \
    git \
    kmod \
    wget \
    python \
    fuse \
    davfs2 \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfuse-dev \
    libpython-dev && \
  apt-get -qqy clean all && \
  echo "user_allow_other" >> /etc/fuse.conf && \
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN wget https://bootstrap.pypa.io/get-pip.py && python get-pip.py

RUN pip install bson git+https://github.com/whole-tale/girderfs@v0.2#egg=girderfs && pip3 install ipython

RUN userdel node && useradd -g 100 -G 100 -u 1000 -s /bin/bash wtuser

COPY migrate.py /girder

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8
