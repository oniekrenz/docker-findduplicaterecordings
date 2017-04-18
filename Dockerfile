FROM ubuntu
MAINTAINER Oliver Niekrenz <oliver@niekrenz.de>
RUN apt-get update && apt-get install -y \
  default-jre \
  locales \
  python \
  unzip \
  wget \
  python-pip \
  python-dev \
  build-essential
RUN locale-gen en_US.UTF-8
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV PYTHONIOENCODING UTF-8
RUN pip install --upgrade pip
RUN pip install pyexcel-ods
RUN mkdir /opt/FindDuplicateRecordings
COPY FindDuplicateRecordings.py /opt/FindDuplicateRecordings
ENTRYPOINT ["python", "/opt/FindDuplicateRecordings/FindDuplicateRecordings.py"]
CMD ["--help"]
