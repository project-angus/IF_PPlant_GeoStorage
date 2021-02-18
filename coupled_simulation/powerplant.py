#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 12 15:17:46 2018

@author: witte
"""

# %% imports

import pandas as pd
import numpy as np
import json
from scipy import interpolate
import logging
from tespy.networks import load_network
from tespy.tools import logger
from tespy.connections import Ref
from tespy.tools.helpers import TESPyNetworkError
from tespy.tools import document_model

logger.define_logging(
    log_path=True, log_version=True, screen_level=logging.WARNING, file_level=logging.WARNING
)
# %% power plant model class


class model:
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
        # load data.json information into objects dictionary (= attributes of
        # the object)
        path = (cd.working_dir + cd.powerplant_path + cd.scenario + '.powerplant_ctrl.json')
        self.wdir = cd.working_dir + cd.powerplant_path
        self.sc = cd.scenario
        with open(path) as f:
            self.__dict__.update(json.load(f))

        # well information
        self.min_well_depth = min_well_depth
        self.num_wells = num_wells

        # pressure limits
        self.p_max = p_max
        self.p_min = p_min

        self.load_tespy_model()

    def load_tespy_model(self):

        # load tespy models with the network_reader module
        self.charge = load_network(self.wdir + self.tespy_charge_path)
        self.charge.set_attr(iterinfo=False)
        self.charge.solve('design', init_only=True)
        self.discharge = load_network(self.wdir + self.tespy_discharge_path)
        self.discharge.set_attr(iterinfo=False)
        self.discharge.solve('design', init_only=True)

        self.power_plant_layout()

    def power_plant_layout(self):
        """
        Power plant layout calculation to determine power plant design point using
        nominal power input/output and nominal pressure as inputs.
        """
        msg = 'Starting power plant layout calculation.'
        logging.debug(msg)

        for mode in ['charge', 'discharge']:

            model = getattr(self, mode)
            pressure_conn = model.get_conn(getattr(self, 'pressure_conn_' + mode))
            massflow_conn = model.get_conn(getattr(self, 'massflow_conn_' + mode))
            power_bus = model.busses[getattr(self, 'power_bus_' + mode)]

            power_bus.set_attr(P=getattr(self, 'power_nominal_' + mode))
            pressure_conn.set_attr(
                p=getattr(self, 'pressure_nominal_' + mode),
                m=Ref(massflow_conn, 1 / self.num_wells, 0)
            )
            massflow_conn.set_attr(m=np.nan)
            model.get_comp(getattr(self, 'pipe_' + mode)).set_attr(
                L=self.min_well_depth
            )
            model.solve('design')
            document_model(model, path=self.wdir + '_report_design_' + mode)
            model.save(self.wdir + self.sc + '_' + mode + '_design')
            m_nom = massflow_conn.m.val_SI
            setattr(self, 'm_nom_' + mode, m_nom)
            setattr(self, 'm_min_' + mode, m_nom * self.massflow_min_rel)
            setattr(self, 'm_max_' + mode, m_nom * self.massflow_max_rel)
            msg = (
                'Nominal mass flow for ' + mode + ' is ' +
                str(m_nom) + ' at nominal power ' +
                str(getattr(self, 'power_nominal_' + mode)) + ' and nominal ' +
                'pressure ' + str(getattr(self, 'pressure_nominal_' + mode)) +
                '.'
            )
            logging.debug(msg)
            model.solve('offdesign', design_path=self.wdir + self.sc + '_' + mode + '_design')
            document_model(model, path=self.wdir + '_report_offdesign_' + mode)

        msg = 'Finished power plant layout calculation.'
        logging.debug(msg)

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

        if pressure + 1e-4 < self.p_min:
            msg = (
                'Pressure is below minimum pressure: min=' + str(self.p_min) +
                ', value=' + str(pressure) + '.'
            )
            logging.error(msg)
            return 0, 0, 0
        elif pressure - 1e-4 > self.p_max:
            msg = (
                'Pressure is above maximum pressure: max=' + str(self.p_max) +
                ', value=' + str(pressure) + '.'
            )
            logging.error(msg)
            return 0, 0, 0

        remeber_mode = mode
        mode = self.mode_lookup[mode]
        model = getattr(self, mode)
        power_nominal = getattr(self, 'power_nominal_' + mode)
        pressure_nominal = getattr(self, 'pressure_nominal_' + mode)
        massflow_nominal = getattr(self, 'm_nom_' + mode)
        massflow_min = getattr(self, 'm_min_' + mode)
        massflow_max = getattr(self, 'm_max_' + mode)

        pressure_conn = model.get_conn(
            getattr(self, 'pressure_conn_' + mode)
        )
        massflow_conn = model.get_conn(
            getattr(self, 'massflow_conn_' + mode)
        )
        power_bus = model.busses[getattr(self, 'power_bus_' + mode)]
        heat_bus = model.busses[getattr(self, 'heat_bus_' + mode)]

        design_path = self.wdir + self.sc + '_' + mode + '_design'

        if abs(power) < abs(power_nominal / 100):
            return 0, 0, 0

        try:
            # for higher stability: allow a maximum stepwidth in pressure of
            # 10 bar
            num = int(abs(pressure - pressure_conn.p.val) // 10) + 1
            pressure_range = np.linspace(pressure, pressure_conn.p.val, num, endpoint=False)
            for pressure_step in pressure_range[::-1]:
                pressure_conn.set_attr(p=pressure_step)
                model.solve(mode='offdesign', design_path=design_path)

            # adjust power value in steps of 10 % relative to nominal power
            massflow_conn.set_attr(m=np.nan)
            num = int(
                abs(power - power_bus.P.val) // abs(0.2 * power_nominal)) + 1
            power_range = np.linspace(power, power_bus.P.val, num, endpoint=False)
            for power_step in power_range[::-1]:
                power_bus.set_attr(P=power_step)
                model.solve(mode='offdesign', design_path=design_path)

            m = massflow_conn.m.val
            heat = heat_bus.P.val
            return self.check_results(
                model, m, massflow_min, massflow_max, power, pressure, heat, remeber_mode)

        except (ValueError, TESPyNetworkError) as e:
            # except general errors in calculation
            msg = (
                'ERROR: Could not find a solution for input pair power=' +
                str(power) + ' pressure=' + str(pressure) + '.'
            )
            print(msg)
            logging.error(msg)
            power_bus.set_attr(P=power_nominal)
            pressure_conn.set_attr(p=pressure_nominal)
            model.solve('offdesign', init_path=design_path, design_path=design_path)
            return 0, 0, 0

    def check_results(self, model, massflow, massflow_min, massflow_max, power, pressure, heat, mode):
        if model.res[-1] > 1e-3:
            msg = (
                'Could not find a solution for input pair power=' + str(power) +
                ' pressure=' + str(pressure) + ', resetting starting values ' +
                'to design point.'
            )
            print(msg)
            raise TESPyNetworkError(msg)
        elif massflow < massflow_min:
            msg = (
                'Mass flow for input pair power=' + str(power) + ' pressure=' +
                str(pressure) + ' below minimum mass flow.'
            )
            print(msg)
            logging.error(msg)
            return 0, 0, 0
        elif massflow > massflow_max:
            msg = (
                'Mass flow for input pair power=' + str(power) + ' pressure=' +
                str(pressure) + ' above maximum mass flow. Adjusting power ' +
                'to match maximum allowed mass flow.'
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
            logging.debug(msg)
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

        if pressure + 1e-4 < self.p_min:
            msg = (
                'Pressure is below minimum pressure: min=' + str(self.p_min) +
                ', value=' + str(pressure) + '.'
            )
            logging.error(msg)
            return 0, 0, 0
        elif pressure - 1e-4 > self.p_max:
            msg = (
                'Pressure is above maximum pressure: max=' + str(self.p_max) +
                ', value=' + str(pressure) + '.'
            )
            logging.error(msg)
            return 0, 0, 0

        remeber_mode = mode
        mode = self.mode_lookup[mode]
        model = getattr(self, mode)
        power_nominal = getattr(self, 'power_nominal_' + mode)
        pressure_nominal = getattr(self, 'pressure_nominal_' + mode)
        massflow_nominal = getattr(self, 'm_nom_' + mode)
        massflow_min = getattr(self, 'm_min_' + mode)
        massflow_max = getattr(self, 'm_max_' + mode)

        pressure_conn = model.get_conn(
            getattr(self, 'pressure_conn_' + mode)
        )
        massflow_conn = model.get_conn(
            getattr(self, 'massflow_conn_' + mode)
        )
        power_bus = model.busses[getattr(self, 'power_bus_' + mode)]
        heat_bus = model.busses[getattr(self, 'heat_bus_' + mode)]

        design_path = self.wdir + self.sc + '_' + mode + '_design'

        if mass_flow < massflow_min - 1e-4:
            msg = (
                'Mass flow is below minimum mass flow, shutting down power ' +
                'plant.'
            )
            print(msg)
            logging.error(msg)
            return 0, 0, 0
        elif mass_flow > massflow_max + 1e-4:
            msg = (
                'Mass flow above maximum mass flow. Adjusting mass flow ' +
                'to maximum allowed mass flow.'
            )
            print(msg)
            logging.warning(msg)
            return self.get_power(massflow_max, pressure, remeber_mode)

        try:
            # for higher stability: allow a maximum stepwidth in pressure of
            # 10 bar
            num = int(abs(pressure - pressure_conn.p.val) // 10) + 1
            pressure_range = np.linspace(pressure, pressure_conn.p.val, num, endpoint=False)
            for pressure_step in pressure_range[::-1]:
                pressure_conn.set_attr(p=pressure_step)
                model.solve(mode='offdesign', design_path=design_path)

            # unset power of bus and set massflow instead
            power_bus.set_attr(P=np.nan)
            # adjust mass flow value in steps of 5 % relative to nominal power
            num = int(
                abs(mass_flow - massflow_conn.m.val) // abs(0.05 * massflow_nominal)) + 1
            mass_flow_range = np.linspace(mass_flow, massflow_conn.m.val, num, endpoint=False)
            for mass_step in mass_flow_range[::-1]:
                massflow_conn.set_attr(m=mass_step)
                model.solve(mode='offdesign', design_path=design_path)

            power = power_bus.P.val
            heat = heat_bus.P.val
            msg = (
                'Calculation successful for mass flow=' + str(mass_flow) +
                ' pressure=' + str(pressure) + '. Power=' + str(power) + '.'
            )
            print(msg)
            logging.debug(msg)
            return mass_flow, power, heat

        except (ValueError, TESPyNetworkError) as e:
            # except general errors in calculation
            msg = (
                'ERROR: Could not find a solution for input pair mass flow=' +
                str(mass_flow) + ' pressure=' + str(pressure) + '.'
            )
            print(msg)
            logging.error(msg)
            massflow_conn.set_attr(m=None)
            power_bus.set_attr(P=power_nominal)
            pressure_conn.set_attr(p=pressure_nominal)
            model.solve('offdesign', init_path=design_path, design_path=design_path)
            return 0, 0, 0
