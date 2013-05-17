#!/bin/bash
# generic user-init script
set -e

PATH="${PATH}:/usr/local/sbin:/usr/sbin:/sbin"
DAEMON="{{component.root.workdir}}/{{component.executable}}"
PIDFILE="{{component.pidfile}}"

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
