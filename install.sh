#!/bin/bash
set -Eeuo pipefail

dir=$(dirname $(realpath -s $(readlink -f $BASH_SOURCE)))

###### Enable SPI and I2C in raspi-config

if [ $(whoami) != 'root' ] ; then
    echo "This script must be run under root"
    exit 1
fi

##### Install and configure ddclient so that the robot can be reached remotely
apt install --no-install-recommends ddclient

cat > /etc/ddhclient.conf << EOF
ssl=yes
protocol=dyndns2, server=domains.google.com, use=web, web=http://checkip.dyndns.org, login=<...>, password=<...> steve.janakj.net
EOF
#####

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

##### Install pyenv for user pi

# Install Python build dependencies so that new Python interpreter versions can
# be built by pyenv

apt install        \
  make             \
  build-essential  \
  libssl-dev       \
  zlib1g-dev       \
  libbz2-dev       \
  libreadline-dev  \
  libsqlite3-dev   \
  wget             \
  curl             \
  llvm             \
  libncursesw5-dev \
  xz-utils         \
  tk-dev           \
  libxml2-dev      \
  libxmlsec1-dev   \
  libffi-dev       \
  liblzma-dev

git clone https://github.com/pyenv/pyenv.git ~/.pyenv
pushd ~/.pyenv
src/configure && make -C src
popd

echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc

echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
echo 'eval "$(pyenv init -)"' >> ~/.bash_profile

# Make sure systemd has access to the Python interpreters installed here
chmod a+rx /root

# Re-login to activate the installation
#####

##### Install Python 3.10.4
pyenv install 3.10.4
#####


##### Create a Python venv for the robot
apt install                \
    libsdl2-dev            \
    libsdl2-image-dev      \
    libsdl2-mixer-dev      \
    libsdl2-ttf-dev        \
    libfreetype6-dev       \
    libportmidi-dev        \
    libcairo-dev           \
    libgirepository1.0-dev \
    libjpeg-dev

python -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements-min.txt
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

###### Install Google Assistant
mkdir -p /srv/assistant
cat > /srv/assistant/credentials.json << "EOF"

    "refresh_token": "<Your refresh token>",
    "token_uri": "https://accounts.google.com/o/oauth2/token",
    "client_id": "<Your client ID>",
    "client_secret": "<Your client secret>",
    "scopes": ["https://www.googleapis.com/auth/assistant-sdk-prototype"]
}
EOF

# Install development dependencies for Google Assistant
apt install portaudio19-dev libffi-dev libssl-dev

# Google Assistant doesn't seem to work with more modern Python versions, so we
# have to restore to 3.8.13 here.
pyenv install 3.8.13

mkdir /srv/assistant
pushd /srv/assistant

# Create a Python 3.8.13 virtual environment and upgrade pip
pyenv local 3.8.13
python -m venv venv
venv/bin/python -m pip install --upgrade pip

# Now install all the pip packages for Google Assistant. Since more modern
# grpcio versions do not have pre-compiled binaries that work on Raspberry Pi
# (they are missing more recent glibc), we select an older grpio version
# manually.
venv/bin/python -m pip install grpcio==1.40.0

# Also install more modern version of the tenacity library which has some async
# stuff fixed.
venv/bin/python -m pip install tenacity==8.0.1

# Now install the various Google Assistant packages
venv/bin/python -m pip install --upgrade google-assistant-sdk[samples]
venv/bin/python -m pip install --upgrade google-auth-oauthlib[tool]

# Install custom applications required by the application
venv/bin/python -m pip install pydbus PyGObject

# The following line is how one can test that the installation works
#googlesamples-assistant-pushtotalk --project-id shaky-steve --device-model-id shaky-steve-l14n6p

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

# Install and configure wireguard tunnel
