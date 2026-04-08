#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 12 15:17:46 2018

@author: witte
"""

from copy import deepcopy
import os
import numpy as np
import json
import logging
from tespy.networks import Network
from tespy.tools.logger import logger
from tespy.connections import Ref
from .powerplant_template import PowerPlant
from tespy.tools.helpers import TESPyNetworkError


logger.setLevel(logging.ERROR)


class PowerPlantCoupling:
    """
    Creates the model for the power plant. Parameters are loaded from
    coupling data object cd.

    Parameters
    ----------
    cd : coupling_data
        Generel data for the interface handling.

    min_well_depth : float
        Depth of the wells.

    num_wells : int
        Number of wells.

    p_max : float
        Maximum pressure limit.

    p_min : float
        Minimum pressure limit.

    Note
    ----
    The depth of the wells along with the number of wells determines the
    dynamic pressure loss in bore hole pipes connecting the power plant with
    the geological storage. The pressure limits are the pressure limits at the
    bottom of the bore holes. These inforamtion are provided in
    the geological storage model control file.
    """

    def __init__(self, cd, min_well_depth, num_wells, p_max, p_min):

        # required for attribute lookup (due to bad naming in powerplant module)
        self.mode_lookup = {
            'charging': 'charge',
            'discharging': 'discharge'
        }

        self.wdir = os.path.join(cd.working_dir, cd.powerplant_path)
        self.sc = cd.scenario
        ctrl_file = os.path.join(self.wdir, f"{cd.scenario}.powerplant_ctrl.json")

        with open(ctrl_file) as f:
            self.config = json.load(f)

        # well information
        self.min_well_depth = min_well_depth
        self.num_wells = num_wells

        # pressure limits
        self.p_max = p_max
        self.p_min = p_min

        self.load_tespy_models()
        self.p_max = p_max
        self.p_min = p_min

    def load_tespy_models(self):

        data = deepcopy(self.config["charge"])
        data["path"] = os.path.join(self.wdir, data["path"])
        charge_path = os.path.join(data["path"], "export.json")
        self.charge_model = PowerPlant.from_json(charge_path, data)
        self.charge_model.nw.solve("design", init_path=self.charge_model._design_path)
        self.charge_model.nw.set_attr(iterinfo=False)

        data = deepcopy(self.config["discharge"])
        data["path"] = os.path.join(self.wdir, data["path"])
        discharge_path = os.path.join(data["path"], "export.json")
        self.discharge_model = PowerPlant.from_json(discharge_path, data)
        self.discharge_model.nw.solve("design", init_path=self.discharge_model._design_path)
        self.discharge_model.nw.set_attr(iterinfo=False)
        self._make_power_plant_layouts()

    def _make_power_plant_layouts(self):
        """
        Power plant layout calculation to determine power plant design point using
        nominal power input/output and nominal pressure as inputs.
        """
        charge_specifications = {
            "ambient_pressure": self.config["general"]["ambient pressure"],
            "ambient_temperature": self.config["general"]["ambient temperature"],
            "well_number": self.config["storage"]["well_num"],
            "well_diameter": self.config["storage"]["well_diameter"],
            "well_depth": self.config["storage"]["well_depth"],
            "power": self.config["charge"]["power_nominal"],
            "well_pressure": self.config["charge"]["pressure_nominal"]
        }
        self.charge_model.solve_model_design(**charge_specifications)
        self.charge_model.save_design_state()
        self.charge_model.solve_model_offdesign()
        self.charge_model.dot_m_nominal = self.charge_model.get_parameter(
            "powerplant_mass_flow"
        )
        self.charge_model.power_nominal = self.charge_model.get_parameter("power")
        self.charge_model.dot_m_min = (
            self.charge_model.dot_m_nominal
            * self.config["charge"]["massflow_min_rel"]
        )
        self.charge_model.dot_m_max = (
            self.charge_model.dot_m_nominal
            * self.config["charge"]["massflow_max_rel"]
        )

        discharge_specifications = {
            "ambient_pressure": self.config["general"]["ambient pressure"],
            "well_number": self.config["storage"]["well_num"],
            "well_diameter": self.config["storage"]["well_diameter"],
            "well_depth": self.config["storage"]["well_depth"],
            "power": self.config["discharge"]["power_nominal"],
            "well_pressure": self.config["discharge"]["pressure_nominal"],
            "well_temperature": self.config["storage"]["temperature"]
        }
        self.discharge_model.solve_model_design(**discharge_specifications)
        self.discharge_model.save_design_state()
        self.discharge_model.solve_model_offdesign()
        self.discharge_model.dot_m_nominal = self.discharge_model.get_parameter(
            "powerplant_mass_flow"
        )
        self.discharge_model.power_nominal = self.discharge_model.get_parameter("power")
        self.discharge_model.dot_m_min = (
            self.discharge_model.dot_m_nominal
            * self.config["discharge"]["massflow_min_rel"]
        )
        self.discharge_model.dot_m_max = (
            self.discharge_model.dot_m_nominal
            * self.config["discharge"]["massflow_max_rel"]
        )

    def _check_pressure_limits(self, pressure, mode):
        if pressure + 1e-4 < self.p_min and mode == 'discharge':
            msg = (
                'Pressure is below minimum pressure: min=' + str(self.p_min) +
                ', value=' + str(pressure) + '.'
            )
            logging.error(msg)
            return False
        elif pressure - 1e-4 > self.p_max and mode == 'charge':
            msg = (
                'Pressure is above maximum pressure: max=' + str(self.p_max) +
                ', value=' + str(pressure) + '.'
            )
            logging.error(msg)
            return 0, 0, 0

        return True

    def get_mass_flow(self, power, pressure, mode):
        """
        Calculate the mass flow at given power input (charging) or
        power output (discharging) and pressure at bottom borehole pressure.

        Parameters
        ----------
        power : float
            Scheduled electrical power input/output of the power plant.

        pressure : float
            Bottom borehole pressure.

        mode : str
            Calculation mode: :code:`mode in ['charging', 'discharging']`.

        Returns
        -------
        mass_flow : float
            Air mass flow from/into the storage.

        power_actual : float
            Actual electrical power input/output of the power plant.
            Differs from scheduled power, if schedule can not be met.
        """
        if mode == 'shut-in':
            return 0, 0, 0

        if not self._check_pressure_limits(pressure, mode):
            return 0, 0, 0

        if mode == "charge":
            model = self.charge_model
        else:
            model = self.discharge_model

        specification = {
            "power": power,
            "well_pressure": pressure,
            "powerplant_mass_flow": None  # unset the mass flow specification
        }
        result = model.solve_model_offdesign_with_stepping(**specification)
        if result:
            if abs(power) < abs(model.power_nominal / 100):
                msg = (f"Target power ({power / 1e6:.2f} MW) is below minimum stable part-load limit")
                print(msg)
                logging.warning(msg)
                return 0, 0, 0

            else:

                mass_flow = model.get_parameter("powerplant_mass_flow")
                heat = model.get_parameter("heat")

                return self._check_results(
                    mass_flow,
                    model.dot_m_min, model.dot_m_max,
                    power, pressure, heat, mode
                )

        else:
            model.nw.print_results()
            msg = f"No solution could be found for input pair {power = }, {pressure = }."
            print(msg)
            logging.warning(msg)
            return 0, 0, 0

    def _check_results(self, massflow, massflow_min, massflow_max, power, pressure, heat, mode):
        if massflow < massflow_min:
            msg = (
                f"Mass flow {massflow} for input pair power={power} "
                f"pressure={pressure} below minimum mass flow {massflow_min}, "
                "shutting down."
            )
            print(msg)
            logging.error(msg)
            return 0, 0, 0
        elif massflow > massflow_max:
            msg = (
                f"Mass flow {massflow} for input pair power={power} "
                f"pressure={pressure} above maximum mass flow {massflow_max}. "
                "Adjusting power to match maximum allowed mass flow."
            )
            print(msg)
            logging.warning(msg)
            return self.get_power(massflow_max, pressure, mode)
        else:
            msg = (
                'Calculation successful for power=' + str(power) +
                ' pressure=' + str(pressure) + '. Mass flow=' + str(massflow) + '.'
            )
            print(msg)
            # logging.debug(msg)
            return massflow, power, heat

    def get_power(self, mass_flow, pressure, mode):
        """
        Calculates the power at given mass flow and pressure in charging or discharging mode.

        Parameters
        ----------
        mass_flow : float
            Mass flow.

        pressure : float
            Bottom borehole pressure.

        mode : str
            Calculation mode: :code:`mode in ['charging', 'discharging']`.

        Returns
        -------
        mass_flow_actual : float
            Actual mass flow of the power plant.

        power : float
            Actual electrical power input/output of the power plant.
        """
        if mode == 'shut-in':
            return 0, 0, 0

        if not self._check_pressure_limits(pressure, mode):
            return 0, 0, 0

        if mode == "charge":
            model = self.charge_model
        else:
            model = self.discharge_model

        mass_flow_min, mass_flow_max = model.dot_m_min, model.dot_m_max,

        if mass_flow < mass_flow_min - 1e-4:
            msg = (
                'Mass flow is below minimum mass flow, shutting down power ' +
                'plant.'
            )
            print(msg)
            logging.error(msg)
            return 0, 0, 0
        elif mass_flow > mass_flow_max + 1e-4:
            msg = (
                f"Mass flow {mass_flow} above maximum mass flow. Adjusting mass flow "
                f"to maximum allowed mass flow of {mass_flow_max}."
            )
            print(msg)
            logging.warning(msg)
            return self.get_power(mass_flow_max, pressure, mode)

        specification = {
            "power": None,
            "well_pressure": pressure,
            "powerplant_mass_flow": mass_flow
        }
        result = model.solve_model_offdesign_with_stepping(**specification)

        if not result:
            return 0, 0, 0

        else:
            power = model.get_parameter("power")
            heat = model.get_parameter("heat")
            return mass_flow, power, heat
