import logging
from threading      import Thread
from gi.repository  import GLib
from pydbus.generic import signal
from pydbus         import SystemBus

log = logging.getLogger(__name__)


class DBusAPI(Thread):
    def __init__(self, bus_name):
        super().__init__()
        self.dbus_loop = None
        self.started = False
        self.bus_name = bus_name

    def start(self):
        super().start()
        self.started = True

    def run(self):
        log.debug(f'Publishing {self.bus_name} on the system DBus')
        self.bus = SystemBus()
        self.bus.publish(self.bus_name, self)

        self.dbus_loop = GLib.MainLoop()
        self.dbus_loop.run()

    def quit(self):
        if self.started:
            log.debug(f'Stopping DBus API for {self.bus_name}')

        if self.dbus_loop is not None:
            self.dbus_loop.quit()

        if self.started:
            self.join()

    PropertiesChanged = signal()
