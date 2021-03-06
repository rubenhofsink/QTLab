# NI_DAQ.py, National Instruments Data AcQuisition instrument driver
# Reinier Heeres <reinier@heeres.eu>, 2009
# Gabriele de Boo <ggdeboo@gmail.com>, 2015
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import types
from lib.dll_support import nidaq
from instrument import Instrument
import qt
import numpy as np
import logging

def _get_channel(devchan):
    if not '/' in devchan:
        return devchan
    parts = devchan.split('/')
    if len(parts) != 2:
        return devchan
    return parts[1]

class NI_DAQ(Instrument):
    '''
    This is the QTLab wrapper for National Instruments data acquisition cards
    '''
    def __init__(self, name, id, samples=100, freq=10000, reset=False):
        '''
        Initializes the daq card

        Input:
            name(string)        : name of the instrument
            id(string)          : device id as set by the NI configuration
            samples(integer)    : the number of samples to take per acquisition
            freq(integer)       : the sampling rate
        
        Output:
            None
        '''
        Instrument.__init__(self, name, tags=['physical'])

        self._id = id
        self.ai_range_list = nidaq.get_input_voltage_ranges(id)
        self.ao_range_list = nidaq.get_output_voltage_ranges(id)
        self.ai_max_rate = nidaq.get_maximum_input_channel_rate(id)
        self.ai_min_rate = nidaq.get_minimum_input_channel_rate(id)
        self.ao_max_rate = nidaq.get_maximum_output_channel_rate(id)
        logging.info('NI daq device type: %s' % nidaq.get_device_type(id))
        logging.info('Voltage ranges on the inputs: ' +
                        str(self.ai_range_list))
        logging.info('Voltage ranges on the outputs: ' +
                        str(self.ao_range_list))
        logging.info('Minimum single channel rate for analog inputs: %.1f kS/s' %
                        (self.ai_min_rate/1000))
        logging.info('Maximum single channel rate for analog inputs: %.1f kS/s' %
                        (self.ai_max_rate/1000))
        logging.info('Maximum channel rate for analog output: %.1f kS/s' %
                        (self.ao_max_rate/1000))
        if nidaq.get_simultaneous_sampling_support(id):
            logging.info('This DAQ supports simultaneous sampling.')
        else:
            logging.info('This DAQ does not support simultaneous sampling.')

        self.add_parameter('chan_config',
            flags=Instrument.FLAG_SET|Instrument.FLAG_SOFTGET,
            type=types.StringType,
            option_list=('Default', 'RSE', 'NRSE', 'Diff', 'PseudoDiff'))

        self.set_chan_config('Diff')

        for ch_in in self._get_input_channels():
            ch_in = _get_channel(ch_in)
            self.add_parameter(ch_in,
                flags=Instrument.FLAG_GET,
                type=np.ndarray,
                units='mV',
                format='%.02f',
                tags=['measure'],
                get_func=self.do_get_input,
                channel=ch_in)

        for ch_out in self._get_output_channels():
            ch_out = _get_channel(ch_out)
            self.add_parameter(ch_out,
                flags=Instrument.FLAG_GETSET,
                type=types.FloatType,
                minval=-10000 , maxval = 10000,
                units='mV',
                format='%.02f',
                tags=['sweep'],
                maxstep=100, stepdelay=50,
                set_func=self.do_set_output,
                get_func=self.do_get_output,
                channel=ch_out)

        for ch_ctr in self._get_counter_channels():
            ch_ctr = _get_channel(ch_ctr)
            self.add_parameter(ch_ctr,
                flags=Instrument.FLAG_GET,
                type=types.IntType,
                units='#',
                tags=['measure'],
                get_func=self.do_get_counter,
                channel=ch_ctr)
            self.add_parameter(ch_ctr + "_src",
                flags=Instrument.FLAG_SET | Instrument.FLAG_SOFTGET,
                type=types.StringType,
                set_func=self.do_set_counter_src,
                channel=ch_ctr)


        self.add_parameter('count_time',
            flags=Instrument.FLAG_SET|Instrument.FLAG_SOFTGET,
            type=types.FloatType,
            units='s')
        #Added by Jan
        self.add_parameter('samples',
            flags=Instrument.FLAG_SET|Instrument.FLAG_SOFTGET,
            type=types.IntType,
            units='#',
            )
        #Added by Jan
        self.add_parameter('freq',
            flags=Instrument.FLAG_SET|Instrument.FLAG_SOFTGET,
            type=types.FloatType,
            units='#/s',
            minval=self.ai_min_rate,maxval=self.ai_max_rate,
            )         

        self.add_function('reset')

        self.set_count_time(0.1)
        self.set_samples(samples)#Added by Jan
        self.set_freq(freq)#Added by Jan

        # Update wrapper with current output value
        # This assumes that the outputs are connected to the inputs that
        # correspond to the output channel + 10!
        self._output = {}
        for ch_out in self._get_output_channels():
            ch_out = _get_channel(ch_out)
            _ch_in = ch_out.replace('o', 'i')
            _ch_in = _ch_in.replace('0', '6')
            _ch_in = _ch_in.replace('1', '7')
            self._output[ch_out] = self.do_get_input(_ch_in)
            #self._output[ch_out] = self.do_get_input(_ch_in[:-1] + '1' + _ch_in[-1])

        if reset:
            self.reset()
        else:
            self.get_all()

    def get_all(self):
        ch_in = [_get_channel(ch) for ch in self._get_input_channels()]
        self.get(ch_in)
        for ch_out in self._get_output_channels():
            ch_out = _get_channel(ch_out)
            self.get(ch_out)

    def reset(self):
        '''Reset device.'''
        nidaq.reset_device(self._id)

    def _get_input_channels(self):
        physical_input_channels = nidaq.get_physical_input_channels(self._id)
        if self.get_chan_config() == 'DIFF':
            return physical_input_channels[:len(physical_input_channels)/2]
        else:
            return physical_input_channels

    def _get_output_channels(self):
        return nidaq.get_physical_output_channels(self._id)

    def _get_counter_channels(self):
        return nidaq.get_physical_counter_channels(self._id)

    def do_get_input(self, channel, average=True, 
                        minvol = -10.0, maxvol = 10.0, 
                        trigger=False,
                        trig_slope='POS',
                        pre_trigger_samples=2,):
        '''Read the specified number of samples from the input.'''
        # Gabriele added the average parameter
        devchan = '%s/%s' % (self._id, channel)
        #Jan added samples=self._samples and freq=self._fraq
        self._pre_trigger_samples = pre_trigger_samples
        if self._pre_trigger_samples < 2 :
            raise ValueError('The number of pre_trigger samples has to be ' +
                                'larger than 1.')
        if self._samples < (self._pre_trigger_samples + 2):
            raise ValueError('The total number of samples has to be larger ' +
                                'than the number of pre trigger samples + 1') 
        values = nidaq.read(devchan, 
                            config=self._chan_config, 
                            samples=self._samples, 
                            freq=self._freq, 
                            averaging=average, 
                            minv=minvol, 
                            maxv=maxvol, 
                            triggered=trigger, 
                            trigger_slope=trig_slope,
                            pre_trig_samples=pre_trigger_samples)
        return (values * 1000.0)

    def do_set_samples(self, samples):
        '''Set the number of samples taken in a single acquisition.'''
        #Added by Jan
        self._samples = samples

    def do_get_samples(self):
        #Added by Jan
        return self._samples

    def do_set_freq(self, freq):
        #Added by Jan
        self._freq = freq

    def do_get_freq(self):
        #Added by Jan
        return self._freq    
        
    def do_set_output(self, val, channel):
        devchan = '%s/%s' % (self._id, channel)
        self._output[channel] = val
        return nidaq.write(devchan, val/1000.0)#/100 for 1:10 divider, /1000 for normal

    def do_get_output(self, channel):
        return self._output[channel]

    def do_set_chan_config(self, val):
        self._chan_config = val

    def do_set_count_time(self, val):
        self._count_time = val

    def do_get_counter(self, channel):
        devchan = '%s/%s' % (self._id, channel)
        src = self.get(channel + "_src")
        if src is not None and src != '':
            src = '/%s/%s' % (self._id, src)
        return nidaq.read_counter(devchan, src=src, freq=1/self._count_time)

    def do_set_counter_src(self, val, channel):
        return True

def detect_instruments():
    '''Refresh NI DAQ instrument list.'''

    for name in nidaq.get_device_names():
        qt.instruments.create('NI%s' % name, 'NI_DAQ', id=name)

