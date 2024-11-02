import logging
from alsaaudio import Mixer, ALSAAudioError, VOLUME_UNITS_RAW
from numpy import cbrt, power

from kalliope.core.NeuronModule import NeuronModule, InvalidParameterException

logging.basicConfig()
logger = logging.getLogger("kalliope")


class SoundManager(object):

    m = {}
    # Master & PCM as per kalliope.neurons.volume; Speaker & Playback as per seeed-voicecard driver
    for mixer_name in ['Master', 'PCM', 'Playback', 'Speaker']:
        if 'default' not in m:
            try:
                m[mixer_name] = Mixer(mixer_name)
                m['default'] = mixer_name
            except ALSAAudioError:
                pass
    if 'default' not in m:
        m['default'] = None

    @classmethod
    def resolve_mixer(cls, mixer_name):
        if mixer_name == 'default':
            mixer_name = cls.m['default']
        if mixer_name is not None:
            if mixer_name not in cls.m:
                try:
                    cls.m[mixer_name] = Mixer(mixer_name)
                except ALSAAudioError:
                    pass
            if mixer_name in cls.m:
                return mixer_name
        return None

    @classmethod
    def set_volume(cls, mixer_name, volume_level):
        if mixer_name == 'default':
            mixer_name = cls.m['default']
        if mixer_name in cls.m and cls.m[mixer_name] is not None:
            mixer_raw_min, mixer_raw_max = cls.m[mixer_name].getrange(units=VOLUME_UNITS_RAW)
            mixer_raw_vol = int(cbrt(volume_level / 100.0) * (mixer_raw_max - mixer_raw_min) + mixer_raw_min)
            cls.m[mixer_name].setvolume(int(mixer_raw_vol), units=VOLUME_UNITS_RAW)

    @classmethod
    def get_volume(cls, mixer_name):
        if mixer_name == 'default':
            mixer_name = cls.m['default']
        if mixer_name in cls.m and cls.m[mixer_name] is not None:
            mixer_raw_min, mixer_raw_max = cls.m[mixer_name].getrange(units=VOLUME_UNITS_RAW)
            mixer_raw_vol = cls.m[mixer_name].getvolume(units=VOLUME_UNITS_RAW)
            if isinstance(mixer_raw_vol, list) is True:
                mixer_raw_vol = mixer_raw_vol[0]
            vol = power(10, (mixer_raw_vol - mixer_raw_max) / 6000.0)
            if mixer_raw_min != -9999999:
                min_norm = power(10, (mixer_raw_min - mixer_raw_max) / 6000.0)
                vol = (vol - min_norm) / (1 - min_norm)
            return int(vol)
        return None


class Normalizedvolume(NeuronModule):

    def __init__(self, **kwargs):
        NeuronModule.__init__(self, **kwargs)

        self.mixer = kwargs.get('mixer', 'default')
        self.level = kwargs.get('level', None)
        self.action = kwargs.get('action', None)
        try:
            self.mute = bool(str(kwargs.get('mute', 'False')).capitalize())
        except ValueError:
            self.mute = False

        # check parameters
        if self._is_parameters_ok():
            if self.action == 'get':
                logger.info("[neuron:normalizedvolume] get volume for '{}': {}%".format(self.mixer, SoundManager.get_volume(self.mixer)))
            if self.action == 'set':
                logger.info("[neuron:normalizedvolume] set volume for '{}' to: {}%".format(self.mixer, self.level))
                SoundManager.set_volume(self.mixer, self.level)
            if self.action == 'raise':
                current_level = SoundManager.get_volume(self.mixer)
                level_to_set = self.level + current_level
                if level_to_set > 100:
                    level_to_set = 100
                logger.info("[neuron:normalizedvolume] set volume for '{}' to: {}%".format(self.mixer, level_to_set))
                SoundManager.set_volume(self.mixer, level_to_set)
            if self.action == 'lower':
                current_level = SoundManager.get_volume(self.mixer)
                level_to_set = current_level - self.level
                if level_to_set < 0:
                    level_to_set = 0
                logger.info("[neuron:normalizedvolume] set volume to: {}%".format(level_to_set))
                SoundManager.set_volume(self.mixer, level_to_set)

            if self.mute is False:
                message = {
                    'asked_level': self.level,
                    'asked_action': self.action,
                    'current_level': SoundManager.get_volume(self.mixer)
                }
                self.say(message)

    def _is_parameters_ok(self):
        mixer_name = self.mixer
        self.mixer = SoundManager.resolve_mixer(mixer_name)
        if self.mixer is None:
            raise InvalidParameterException("[neuron:normalizedvolume] non-existant mixer '{}'".format(mixer_name))
        if self.action is None:
            raise InvalidParameterException("[neuron:normalizedvolume] action needs to be set")
        if self.action not in ["get", "set", "raise", "lower"]:
            raise InvalidParameterException("[neuron:normalizedvolume] action can be 'get', 'set', 'raise' or 'lower'")
        if self.action != 'get' and self.level is None:
            raise InvalidParameterException("[neuron:normalizedvolume] level needs to be set (except for 'get')")
        try:
            self.level = int(self.level)
        except ValueError:
            raise InvalidParameterException("[neuron:normalizedvolume] level '{}' is not a valid integer".format(self.level))
        if self.level < 0 or self.level > 100:
            raise InvalidParameterException("[neuron:normalizedvolume] level needs to be placed between 0 and 100")
        return True

