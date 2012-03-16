#!/bin/bash
# generic user-init script
#
# Copyright (c) 2012 gocept gmbh & co. kg
# See also LICENSE.txt
set -e

PATH="${d}{PATH}:/usr/local/sbin:/usr/sbin:/sbin"
DAEMON="${component.root.compdir}/${component.executable}"
PIDFILE="${component.root.compdir}/${component.pidfile}"

start() {
    start-stop-daemon --start -p "$PIDFILE" -i -- "$DAEMON"
}

stop() {
    start-stop-daemon --stop -p "$PIDFILE"
}

status() {
    start-stop-daemon --status -p "$PIDFILE"
}

case $1 in
    start|stop|status)
        $1;;
    restart)
        stop || true
        start
        ;;
    *)
        echo "$0: unknown command '$1'" >&2
        ;;
esac
