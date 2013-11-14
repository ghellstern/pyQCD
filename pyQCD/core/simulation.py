from lattice import Lattice
from config import Config
from propagator import Propagator
from wilslps import WilsonLoops
from dataset import DataSet

import xml.etree.ElementTree as ET
import numpy as np
import sys
import time
import inspect
import warnings
        
def makeParseError(msg):
    out = ET.ParseError()
    out.msg = msg
    out.filename = __file__
    out.lineno = inspect.currentframe().f_back.f_lineno
            
    return out

class Simulation(object):
    
    xml_meas_dict = {"propagator": (Propagator, "get_propagator"),
                     "wilson_loops": (WilsonLoops, "get_wilson_loops"),
                     "configuration": (Config, "get_config")}
    
    def __init__(self, num_configs, measurement_spacing, num_warmup_updates,
                 update_method="heatbath", run_parallel=True, rand_seed=-1,
                 verbosity=1):
        """Creates and returns a simulation object
        
        :param num_configs: The number of configurations on which to perform
        measurements
        :type num_configs: :class:`int`
        :param measurement_spacing: The number of updates between measurements
        :type measurement_spacing: :class:`int`
        :param num_warmup_updates: The number of updates used to thermalize
        the lattice
        :type num_warmup_updates: :class:`int`
        :param update_method: The method used to update the lattice; current
        supported methods are "heatbath", "staple_metropolis" and "metropolis"
        :type update_method: :class:`str`
        :param run_parallel: Determines whether OpenMP is used when updating
        the lattice
        :type run_parallel: :class:`bool`
        :param rand_seed: The random number seed used for performing updates;
        -1 results in the current time being used
        :type rand_seed: :class:`int`
        :param verbosity: The level of verbosity when peforming the simulation,
        with 0 producing no output, 1 producing some output and 2 producing the
        most output, such as details of propagator inversions
        :type verbosity: :class:`int`
        """
        
        self.num_configs = num_configs
        self.measurement_spacing = measurement_spacing
        self.num_warmup_updates = num_warmup_updates
        
        self.update_method = update_method
        self.run_parallel = run_parallel
        self.rand_seed = rand_seed
        self.verbosity = verbosity
        
        self.use_ensemble = False
        
        self.measurements = {}
    
    def create_lattice(self, L, T, action, beta, u0=1.0, block_size=None):
        """Creates a Lattice instance to use in the simulation
        
        :param L: The lattice spatial extent
        :type L: :class:`int`
        :param T: The lattice temporal extent
        :type T: :class:`int`
        :param action: The gauge action to use in gauge field updates
        :type action: :class:`str`
        :param beta: The inverse coupling to use in the gauge action
        :type beta: :class:`float`
        :param u0: The mean link to use in tadpole improvement
        :type u0: :class:`float`
        :param block_size: The sub-lattice size to use when performing gauge
        field updates in parallel
        """
        
        self.lattice = Lattice(L, T, beta, u0, action, self.measurement_spacing,
                               self.update_method, self.run_parallel,
                               block_size, self.rand_seed)
    
    def load_ensemble(self, filename):
        """Loads a gauge configuration dataset to use in the simulation
        
        :param filename: The ensemble file
        :type filename: :class:`str`
        """
        
        if not hasattr(self, "lattice"):
            AttributeError("A lattice must be defined before an ensemble may "
                           "be loaded.")
        
        ensemble = DataSet.load(Config, filename)
        
        if ensemble.num_data != self.num_configs:
            raise AttributeError("Number of configutations in ensemble ({}) "
                                 "does not match the required number of "
                                 "simulation configurations ({})."
                                 .format(ensemble.num_data, self.num_configs))
        elif self.lattice.L != ensemble.get_datum(0).L:
            raise AttributeError("Ensemble spatial extent ({}) does not match "
                                 "the specified lattice spatial extent ({})."
                                 .format(ensemble.get_datum(0).L,
                                         self.lattice.L))
        elif self.lattice.T != ensemble.get_datum(0).T:
            raise AttributeError("Ensemble temporal extent ({}) does not match "
                                 "the specified lattice temporal extent ({})."
                                 .format(ensemble.get_datum(0).T,
                                         self.lattice.T))
        else:
            self.ensemble = ensemble
            self.use_ensemble = True
    
    def add_measurement(self, meas_type, meas_file, **kwargs):
        """Adds a measurement to the simulation to be performed when the
        simulation is run
        
        Possible parameters (depending on :samp:`meas_type`):
        
        :param meas_type: The class corresponding to the measurement to be
        performed
        :type meas_type: :class:`type`
        :param meas_file: The :class:`DataSet` file in which to store the
        measurement
        :param mass: The mass to use if a propagator is to be calculated
        :type mass: :class:`float`
        :param source_site: The source site to use when computing a propagator
        (default it [0, 0, 0, 0])
        :type source_site: :class:`list`
        :param num_field_smears: The number of times to stout smear the gauge
        (default is 0)
        field before performing a measurement
        :type num_field_smears: :class:`int`
        :param field_smearing_param: The stout smearing parameter default is 1.0
        :type field_smearing_param: :class:`float`
        :param num_source_smears: The number of Jacobi smears to apply to the
        source when computing a propagator (default is 0)
        :type num_source_smears: :class:`int`
        :param source_smearing_param: The smearing parameter to use when
        smearing the source (default is 1.0)
        :type source_smearing_param: :class:`float`
        :param num_sink_smears: The number of Jacobi smears to apply to the
        sink when computing a propagator (default is 0)
        :type num_sink_smears: :class:`int`
        :param sink_smearing_param: The smearing parameter to use when
        smearing the sink (default is 1.0)
        :type sink_smearing_param: :class:`float`
        :param solver_method: The method to use when computing a propagator, may
        either be "bicgstab" or "conjugate_gradient" (default "bicgstab")
        :type sink_smearing_param: :class:`str`
        """
        
        if meas_type == Config:
            dataset = DataSet(meas_type, meas_file)
            message = "Saving field configuration"
            function = "get_config"
            
            self.measurements.update([(message, (kwargs, dataset, function))])
        
        elif meas_type == WilsonLoops:
            dataset = DataSet(meas_type, meas_file)
            message = "Computing wilson loops"
            function = "get_wilson_loops"
            
            self.measurements.update([(message, (kwargs, dataset, function))])
            
        elif meas_type == Propagator:
            dataset = DataSet(meas_type, meas_file)
            message = "Computing propagator"
            function = "get_propagator"
            
            if self.verbosity > 0:
                kwargs.update([("verbosity", self.verbosity - 1)])
            else:
                kwargs.update([("verbosity", 0)])
            
            self.measurements.update([(message, (kwargs, dataset, function))])
            
        else:
            raise TypeError("Measurement data type {} is not understood"
                            .format(meas_type))
    
    def _do_measurements(self, save=True):
        """Iterate through self.measurements and gather results"""
        
        keys = self.measurements.keys()
        
        for key in keys:
            if self.verbosity > 0:
                if self.measurements[key][2] == "get_propagator":
                    print("- {}...".format(key))
                else:
                    print("- {}...".format(key)),
                    
                sys.stdout.flush()
            
            measurement = getattr(self.lattice, self.measurements[key][2]) \
              (**self.measurements[key][0])
            
            if save:
                self.measurements[key][1].add_datum(measurement)
            
            
            if self.verbosity > 0:
                if self.measurements[key][2] == "get_propagator":
                    print("  Done!")
                else:
                    print(" Done!")
                    
                sys.stdout.flush()
    
    def run(self, timing_run=False, num_timing_configs=10, store_plaquette=True):
        """Runs the simulation
        
        :param timing_run: Performs a number of trial updates and measurements
        to estimate the total wall clock time of the simulation
        :type timing_run: :class:`bool`
        :param num_timing_configs: The number of updates and measurements used
        to estimate the total wall clock time
        :type num_timing_configs: :class:`int`
        """
        
        if store_plaquette:
            self.plaquettes = np.zeros(self.num_configs)
        
        t0 = time.time()
        
        if self.verbosity > 0:
            print(self)
            print("")
        
        if not self.use_ensemble:
            if self.verbosity > 0:
                print("Thermalizing lattice..."),
                sys.stdout.flush()
        
            self.lattice.thermalize(self.num_warmup_updates)
        
            if self.verbosity > 0:
                print(" Done!")
                
        if timing_run:
            N = num_timing_configs
        else:
            N = self.num_configs
            
        t1 = time.time()
            
        for i in xrange(N):
            if self.verbosity > 0:
                print("Configuration: {}".format(i))
                sys.stdout.flush()
            
            if self.use_ensemble:
                if self.verbosity > 0:
                    print("Loading gauge field..."),
                    sys.stdout.flush()
                    
                config = self.ensemble.get_datum(i)
                self.lattice.set_config(config)
                
                if self.verbosity > 0:
                    print(" Done!")
            
            else:
                if self.verbosity > 0:
                    print("Updating gauge field..."),
                    sys.stdout.flush()
                    
                self.lattice.next_config()
                
                if self.verbosity > 0:
                    print(" Done!")
                    
            if store_plaquette:
                self.plaquettes[i] = self.lattice.av_plaquette()
                if self.verbosity > 0:
                    print("Average plaquette: {}"
                          .format(self.plaquettes[i]))
                    
            if self.verbosity > 0:
                print("Performing measurements...")
                sys.stdout.flush()
            self._do_measurements(not timing_run)
            
        t2 = time.time()
        
        if self.verbosity > 0:
        
            total_time = (t2 - t1) / N * self.num_configs + t1 - t0 \
              if timing_run else t2 - t0
          
            hrs = int((total_time) / 3600)
            mins = int((total_time - 3600 * hrs) / 60)
            secs = total_time - 3600 * hrs - 60 * mins
    
            if timing_run:
                print("Estimated run time: {} hours, {} minutes and {} seconds"
                      .format(hrs, mins, secs))
            else:
                print("Simulation completed in {} hours, {} minutes and {} "
                      "seconds".format(hrs, mins, secs))
            
    @classmethod
    def load(cls, filename):
        """Creates a simulation object based on the supplied xml configuration
        file
        
        :param filename: The file name of the xml input file
        :type filename: :class:`str`
        :returns: :class:`Simulation`
        """
        
        # Wee function to correctly compose ParseError
        
        xmltree = ET.parse(filename)
        xmlroot = xmltree.getroot()
        
        if xmlroot.tag != "pyQCD":
            raise makeParseError("Supplied xml file {} contains no <pyQCD> tag"
                                 .format(filename))
        
        raise_ParseError \
          = '''raise makeParseError("Supplied xml file {} does not specify "
                                    "any {} settings; there is no "
                                    "<{}> tag".format(filename, root_element.tag,
                                                      root_element.tag))'''
        
        show_warning \
          = 'warnings.warn("Xml file has no <{}> tag".format(root_element.tag))'
        
        # First set up a simulation object. To do so we need to extract the
        # simulation settings from the XML file
        
        simulation_settings = xmlroot.find("simulation")
        required_options = ["num_configs", "measurement_spacing",
                            "num_warmup_updates"]
        optional_options = ["update_method", "run_parallel", "rand_seed",
                            "verbosity", "ensemble"]
            
        simulation_dict \
          = Simulation._settings_to_dict(simulation_settings, required_options,
                                         optional_options, raise_ParseError)
        
        use_ensemble = False
        if simulation_dict.has_key("ensemble"):
            ensemble_file = simulation_dict.pop("ensemble")
            use_ensemble = True
        
        simulation = Simulation(**simulation_dict)
        
        lattice_settings = xmlroot.find("lattice")
        required_options = ["L", "T", "action", "beta"]
        optional_options = ["u0", "block_size"]
        
        lattice_dict \
          = Simulation._settings_to_dict(lattice_settings, required_options,
                                         optional_options, show_warning)
        
        simulation.create_lattice(**lattice_dict)
        
        if use_ensemble:
            simulation.load_ensemble(ensemble_file)
            
        measurement_settings = xmlroot.find("measurements")
        
        if measurement_settings != None:        
            for measurement in measurement_settings:
                settings = [setting.tag for setting in measurement]
                meas_name = measurement.tag
                meas_dict = Simulation._settings_to_dict(measurement, settings, [], "None")
                
                meas_file = meas_dict.pop("filename")
                
                simulation.add_measurement(Simulation.xml_meas_dict[meas_name][0],
                                           meas_file, **meas_dict)
            
        return simulation
    
    @staticmethod
    def _settings_to_dict(root_element, required_tags, optional_tags, fail_code):
        """Loads the supplied options found in the root_element into a dict"""
        
        if root_element == None:
            eval(fail_code)
        else:            
            option_keys = []
            option_values = []
            
            for option in required_tags:
                current_element = root_element.find(option)
                
                if current_element == None:
                    raise makeParseError("{} settings missing required "
                                         "tag {}".format(root_element.tag.capitalize(),
                                                         option))
                else:
                    option_keys.append(option)
                    try:
                        option_values.append(eval(current_element.text))
                    except NameError:
                        option_values.append(current_element.text)
                    
            for option in optional_tags:
                current_element = root_element.find(option)
                
                if current_element != None:
                    option_keys.append(option)
                    try:
                        option_values.append(eval(current_element.text))
                    except NameError:
                        option_values.append(current_element.text)
                    
        return dict(zip(option_keys, option_values))
    
    def __str__(self):
        
        out = \
          "Simulation Settings\n" \
          "-------------------\n" \
          "Number of configurations: {}\n" \
          "Measurement spacing: {}\n" \
          "Thermalization updates: {}\n" \
          "Update method: {}\n" \
          "Use OpenMP: {}\n" \
          "Random number generator seed: {}\n" \
          "\n" \
          "Lattice Settings\n" \
          "----------------\n" \
          "Spatial extent: {}\n" \
          "Temporal extent: {}\n" \
          "Gauge action: {}\n" \
          "Inverse coupling (beta): {}\n" \
          "Mean link (u0): {}\n" \
          "Parallel sub-lattice size: {}\n" \
          "\n".format(self.num_configs, self.measurement_spacing,
                      self.num_warmup_updates, self.update_method,
                      self.run_parallel, self.rand_seed, self.lattice.L,
                      self.lattice.T, self.lattice.action, self.lattice.beta,
                      self.lattice.u0, self.lattice.block_size)
        
        for measurement in self.measurements.values():
            heading_underline \
              = (len(measurement[1].datatype.__name__) + 21) * "-"
            meas_settings = \
              "{} Measurement Settings\n" \
              "{}\n".format(measurement[1].datatype.__name__, heading_underline)
            
            meas_settings \
              = "".join([meas_settings,
                         "Filename: {}\n".format(measurement[1].filename)])
                
            for key, value in measurement[0].items():
                meas_settings = "".join([meas_settings,
                                        "{}: {}\n".format(key, value)])
                
        
            out = "".join([out, meas_settings])
            
        return out
