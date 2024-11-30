#!/bin/bash
set -Eeuo pipefail

dir=$(dirname $(realpath -s $(readlink -f $BASH_SOURCE)))

###### PREREQUISITE: Enable SPI and I2C in raspi-config

if [ $(whoami) != 'root' ] ; then
    echo "This script must be run under root"
    exit 1
fi

###### Enable ssh server
systemctl enable ssh
# Don't forget to disable password authentication

# Announce the SSH service via ZeroConf
cat > /etc/avahi/services/ssh.service << "EOF"
<?xml version="1.0" standalone='no'?><!--*-nxml-*-->
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<!--
  This file is part of avahi.

  avahi is free software; you can redistribute it and/or modify it
  under the terms of the GNU Lesser General Public License as
  published by the Free Software Foundation; either version 2 of the
  License, or (at your option) any later version.

  avahi is distributed in the hope that it will be useful, but
  WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
  General Public License for more details.

  You should have received a copy of the GNU Lesser General Public
  License along with avahi; if not, write to the Free Software
  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA
  02111-1307 USA.
-->

<!-- See avahi.service(5) for more information about this configuration file -->

<service-group>

  <name replace-wildcards="yes">%h</name>

  <service>
    <type>_ssh._tcp</type>
    <port>22</port>
  </service>

</service-group>
EOF
#####

##### Install seeed-voicecard
# Install the kernel drivers for the seeed studio voice card. Make sure to
# switch to the correct branch for the Linux kernel version used in Raspberry
# OS.
cd seeed-voicecard
./install.sh
# Reboot the Raspberry Pi now
#####

##### Create a Python virtual environment for the robot software
apt install                \
    libsdl2-dev            \
    libsdl2-image-dev      \
    libsdl2-mixer-dev      \
    libsdl2-ttf-dev        \
    libfreetype6-dev       \
    libportmidi-dev        \
    libcairo-dev           \
    libgirepository1.0-dev \
    libjpeg-dev            \
    libspeexdsp-dev

python -m venv venv
PYTHON=venv/bin/python
$PYTHON -m pip install --upgrade pip

# If you are on a platform unspported by speexdsp-ns, you may need to manually
# compile and install the library as follows:
#
#pushd speexdsp-ns-python
#CPPFLAGS=-I<path> LDFLAGS=-L<path> $PYTHON -m pip pip install . 
#popd

$PYTHON -m pip install -r requirements.txt
$PYTHON -m pip install -e .

# Optionally install Jupyter Lab dependencies
#$PYTHON -m pip install -e '.[jupyter]'
#####

###### Build and install spacenavd for the 3D mouse
pushd spacenavd
./configure
make
make install
popd
######

###### Build and install libspnav for the 3D mouse
pushd libspnav
./configure
make
make install
popd
######

###### Activate all services
cat > /etc/dbus-1/system.d/steve.conf << "EOF"
<!DOCTYPE busconfig PUBLIC
 "-//freedesktop//DTD D-BUS Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
    <policy user="root">
        <allow own_prefix="net.janakj.steve"/>
        <allow send_destination="net.janakj.steve.RoboArm"/>
        <allow receive_sender="net.janakj.steve.RoboArm"/>
        <allow send_interface="net.janakj.steve.RoboArm"/>

        <allow send_destination="net.janakj.steve.LED"/>
        <allow receive_sender="net.janakj.steve.LED"/>
        <allow send_interface="net.janakj.steve.LED"/>

        <allow send_destination="net.janakj.steve.Assistant"/>
        <allow receive_sender="net.janakj.steve.Assistant"/>
        <allow send_interface="net.janakj.steve.Assistant"/>

        <allow send_destination="net.janakj.steve.SpeechToText"/>
        <allow receive_sender="net.janakj.steve.SpeechToText"/>
        <allow send_interface="net.janakj.steve.SpeechToText"/>
    </policy>
    <policy user="pi">
        <allow own_prefix="net.janakj.steve"/>
        <allow send_destination="net.janakj.steve.RoboArm"/>
        <allow receive_sender="net.janakj.steve.RoboArm"/>
        <allow send_interface="net.janakj.steve.RoboArm"/>

        <allow send_destination="net.janakj.steve.LED"/>
        <allow receive_sender="net.janakj.steve.LED"/>
        <allow send_interface="net.janakj.steve.LED"/>

        <allow send_destination="net.janakj.steve.Assistant"/>
        <allow receive_sender="net.janakj.steve.Assistant"/>
        <allow send_interface="net.janakj.steve.Assistant"/>

        <allow send_destination="net.janakj.steve.SpeechToText"/>
        <allow receive_sender="net.janakj.steve.SpeechToText"/>
        <allow send_interface="net.janakj.steve.SpeechToText"/>
    </policy>
</busconfig>
EOF

cat > /etc/udev/rules.d/50-steve-joystick.rules << EOF
SUBSYSTEMS=="usb", ACTION=="add", ATTRS{idVendor}=="046d", ATTRS{idProduct}=="c215", TAG+="systemd", ENV{SYSTEMD_WANTS}+="steve-joystick.service"
EOF

cat > /etc/udev/rules.d/50-steve-navigator.rules << EOF
SUBSYSTEMS=="usb", ACTION=="add", ATTRS{idVendor}=="047d", ATTRS{idProduct}=="c225", TAG+="systemd", ENV{SYSTEMD_WANTS}+="steve-navigator.service"
EOF

for service in spacenavd roboarm led navigator joystick assistant main ; do
    sudo systemctl enable $dir/systemd/steve-$service.service
done
######

cat > /usr/local/bin/steve << "EOF"
#!/bin/bash

cd /srv/steve
exec venv/bin/python shell.py
EOF
chmod a+x /usr/local/bin/steve
