#!/bin/sh

[ "$EXEC_TOOL" ] || EXEC_TOOL=gosu
[ "$COPYCAT_HOST" ] || COPYCAT_HOST=0.0.0.0
[ "$COPYCAT_PORT" ] || COPYCAT_PORT=8080
[ "$COPYCAT_PATH" ] || COPYCAT_PATH=/data

set -e

case "$COPYCAT_PATH" in
    /*) ;;
    *)
        echo "COPYCAT_PATH must be an absolute path. Got '${COPYCAT_PATH}'."
        exit 1
        ;;
esac

case "$COPYCAT_PATH" in
    /|/app|/usr|/etc|/var|/bin|/sbin|/root|/home)
        echo "Refusing unsafe COPYCAT_PATH '${COPYCAT_PATH}'."
        exit 1
        ;;
esac

echo "\
======================================
========= Welcome to CopyCat =========
======================================
"

echo "Using CopyCat data directory: ${COPYCAT_PATH}"

copycat_command="python -m \
                  uvicorn \
                  main:app \
                  --app-dir server \
                  --host ${COPYCAT_HOST} \
                  --port ${COPYCAT_PORT} \
                  --proxy-headers \
                  --forwarded-allow-ips '*'"

if [ "$(id -u)" -eq 0 ] && [ "$(id -g)" -eq 0 ]; then
    echo Setting file permissions...
    chown -R ${PUID}:${PGID} ${COPYCAT_PATH}

    echo Starting CopyCat as user ${PUID}...
    exec ${EXEC_TOOL} ${PUID}:${PGID} ${copycat_command}
else
    echo "A user was set by docker, skipping file permission changes."
    echo Starting CopyCat as user "$(id -u)"...
    exec ${copycat_command}
fi
