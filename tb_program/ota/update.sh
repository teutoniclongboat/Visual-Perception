#!/bin/sh

#
#   tmp.tar.gz
#     |_ home -> (app)
#     |_ firmware -> (bitstream)
#     |_ opt
#     |    |_ lib -> (ivas library)
#     |    |_ share
#     |          |_ ivas -> (ivas configuration)
#     |          |_ models -> (ai model)
#     |_ lib -> (user library)
#

# if [ "$(id -u)" -ne 0 ]; then
#     echo "This script must be run as root" >&2
#     exit 1
# fi

# chown -R petalinux *
# chgrp -R petalinux *

for x in "/home/root/ota/kv260_all/*";
do
    case $x in
        *home)
            if [ -e "$x" ]; then
                cp -fr $x/* /home/root
            fi
            ;;
        *firmware)
            if [ -e "$x" ]; then
                cp -fr $x/* /lib/firmware/xilinx
            fi
            ;;
        *opt)
            if [ -d "$x/lib" ]; then
                cp -fr $x/lib/* /opt/xilinx/lib
            fi
            if [ -d "$x/share/ivas" ]; then
                cp -fr $x/share/ivas/* /opt/xilinx/share/ivas
            fi
            if [ -d "$x/share/models" ]; then
                cp -fr $x/share/models/* /opt/xilinx/share/vitis_ai_library/models
            fi
            ;;
        *lib)
            if [ -e "$x" ]; then
                cp -fr $x/* /usr/lib
            fi
            ;;
    esac
done
