#!/bin/bash

set -e
export DEBIAN_FRONTEND=noninteractive

update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
locale-gen

apt-get --force-yes -qy update
apt-get --force-yes -qy install \
    mercurial
#     postgresql postgresql-server-dev-9.3 \
#     python-virtualenv python-dev swig libssl-dev python-m2crypto \
#     nginx-full \
      
#     vim \
#     build-essential libicu-dev mysql-server  \
#     libldap2-dev libsasl2-dev libmysqlclient-dev \
#     libdb5.1-dev db5.1-util libdb5.1 \
#     libicu-dev build-essential \
#     libxml2-dev libxslt1-dev \
#     lib32bz2-1.0 \
#     lib32gcc1 \
#     libc6-i386 \


# # XXX The whole database management stuff should be done by the deployment code.

# POSTGRESQL_PASSWORD="asdf"
# echo "CREATE ROLE dir2 WITH PASSWORD '$POSTGRESQL_PASSWORD' LOGIN CREATEDB;" | sudo -u postgres psql

# sudo -u postgres createdb -E utf-8 --lc-ctype=en_US.UTF-8 --lc-collate=en_US.UTF-8 -O dir2 directory
# echo "localhost:*:*:dir2:$POSTGRESQL_PASSWORD" > ~vagrant/.pgpass
# chown vagrant: ~vagrant/.pgpass
# chmod 600 ~vagrant/.pgpass

# # mysql -u root works without password
# echo "CREATE DATABASE serverconfig" | mysql -u root

# # XXX You need manually to run
# # ./deployment/work/adminui/bin/initialize_directory2_db admin.ini#aplication
# # inside the VM after the first batou run.

# mkdir -p /run/local
# chown vagrant: /run/local

# rm -rf /etc/nginx/local
# ln -s /etc/nginx/sites-enabled /etc/nginx/local
# chown vagrant: /etc/nginx/sites-enabled
# sed -i 's#sites-enabled/\*;#sites-enabled/*.conf;#' /etc/nginx/nginx.conf

# mkdir -p /etc/nagios/nrpe/local/
# chown vagrant: /etc/nagios/nrpe/local/

# chown -R vagrant: ~vagrant/deployment
