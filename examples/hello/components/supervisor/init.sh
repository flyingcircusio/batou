#!/bin/bash
# user-init script for supervisord
#
# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt
set -e

PATH="${d}{PATH}:/usr/local/sbin:/usr/sbin:/sbin"
DAEMON="${component.compdir}/bin/supervisord"
CTL="${component.compdir}/bin/supervisorctl"
PIDFILE="${component.compdir}/var/supervisord.pid"

start() {
    start-stop-daemon --start -p "$PIDFILE" -i -- "$DAEMON"
}

stop() {
    "$CTL" shutdown
}

restart() {
    "$CTL" restart all
}

status() {
    "$CTL" status
}

case $1 in
    start|stop|status)
        $1;;
    restart)
        restart || {
            stop || true
            start
        }
        ;;
    *)
        echo "$0: unknown command '$1'" >&2
        ;;
esac
