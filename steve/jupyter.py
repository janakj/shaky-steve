from steve.color import RGB, rgb_to_css
import ipywidgets as widgets

led_html = '''
<div style="display: flex; justify-content: center; align-items: center; width: 70px; height: 70px; background-color: black; border-radius: 100%">
    <div style="margin-top: -2px; font-size: 70px; text-align: center; line-height: 1">&#9679;</div>
</div>'''


class LED:
    '''A LED emulated with Jupyter's ipywidgets
    '''
    def __init__(self):
        self._widget = widgets.HTML(value=led_html)
        self.color = RGB(0, 0, 0)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self._widget.style.text_color = rgb_to_css(color)
        self._color = color

    def _repr_mimebundle_(self, *args, **kwargs):
        return self._widget._repr_mimebundle_(*args, **kwargs)

    def __repr__(self):
        return self._widget.__repr__()

    def __str__(self):
        return self._widget.__str__()


class LEDs:
    '''A collection of four LEDs emulating the robot's status LEDs
    '''
    def __init__(self):
        self.led = [LED(), LED(), LED(), LED()]
        self._hbox = widgets.HBox([led._widget for led in self.led])

    def __getitem__(self, key):
        return self.led[key]

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        for led in self.led:
            led.color = color
        self._color = color

    def _repr_mimebundle_(self, *args, **kwargs):
        return self._hbox._repr_mimebundle_(*args, **kwargs)

    def __repr__(self):
        return self._hbox.__repr__()

    def __str__(self):
        return self._hbox.__str__()


class Servo:
    '''A servo emulated with Jupyter's ipywidgets
    '''
    def __init__(self, description, min, max, type='angular', step=0.1):
        self._widget = widgets.FloatSlider(
            min=min, max=max, description=description,
            step=step, readout=True, readout_format='.1f', continuous_update=False)
        self._widget.disabled = True
        self.type = type

    def power_off(self):
        self.set(None)

    def get(self):
        return self._widget.value

    def set(self, state: float | None):
        if state is None:
            self._widget.disabled = True
        else:
            self._widget.disabled = False
            self._widget.value = state

    def _repr_mimebundle_(self, *args, **kwargs):
        return self._widget._repr_mimebundle_(*args, **kwargs)

    def __repr__(self):
        return self._widget.__repr__()

    def __str__(self):
        return self._widget.__str__()


class Servos:
    '''A collection of servos emulating a robotic arm with six degrees of freedom.
    '''
    def __init__(self):
        self.torso = Servo('Torso', -90, 90, type='angular')
        self.clamp = Servo('Clamp', 0, 1, type='linear', step=0.01)
        self.wrist_lr = Servo('Wrist ⇆', -90, 90, type='angular')
        self.wrist_ud = Servo('Wrist ⇅', -90, 90, type='angular')
        self.elbow = Servo('Elbow', -58.4, 61.7, type='angular')
        self.shoulder = Servo('Shoulder', -90, 90, type='angular')
        self._vbox = widgets.VBox([
            self.torso._widget,
            self.clamp._widget,
            self.wrist_lr._widget,
            self.wrist_ud._widget,
            self.elbow._widget,
            self.shoulder._widget
        ])

    def power_off(self):
        self.torso.power_off()
        self.clamp.power_off()
        self.wrist_lr.power_off()
        self.wrist_ud.power_off()
        self.elbow.power_off()
        self.shoulder.power_off()

    def _repr_mimebundle_(self, *args, **kwargs):
        return self._vbox._repr_mimebundle_(*args, **kwargs)

    def __repr__(self):
        return self._vbox.__repr__()

    def __str__(self):
        return self._vbox.__str__()
