#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# %% imports

from tespy import nwk, cmp, con, hlp
from coupled_simulation import cp, pp
from nose.tools import eq_, raises
import numpy as np
import shutil
import os

# %% component tests


class powerplant_tests:

    def setup(self):
        self.cd = cp.coupling_data(os.getcwd() + '/tests/testcase.main_ctrl.json')
        self.cd.powerplant_path = self.cd.powerplant_path.replace('\\', '/')

        path = os.getcwd() + '/tests/' + self.cd.powerplant_path + '/testcase_charge_design'
        if os.path.isdir(path):
            # delete files
            shutil.rmtree(path, ignore_errors=True)

        path = os.getcwd() + '/tests/' + self.cd.powerplant_path + '/testcase_discharge_design'
        if os.path.isdir(path):
            # delete files
            shutil.rmtree(path, ignore_errors=True)

        well_depth = 750
        num_wells = 10
        p_min = 40
        p_max = 80
        self.model = pp.model(self.cd, well_depth, num_wells, p_max, p_min)

    def setup_lut_charging(self):
        # calculate power for corners of lut
        pow_min_ch = []
        pow_min_ch += [self.model.get_power(self.model.m_min_charge, self.model.p_min, 'charging')[1]]
        pow_min_ch += [self.model.get_power(self.model.m_min_charge, self.model.p_max, 'charging')[1]]
        pow_max_ch = []
        pow_max_ch += [self.model.get_power(self.model.m_max_charge, self.model.p_min, 'charging')[1]]
        pow_max_ch += [self.model.get_power(self.model.m_max_charge, self.model.p_max, 'charging')[1]]

        # change model to lut
        self.model.method = 'lut'
        self.model.load_lut_model()

        return pow_min_ch, pow_max_ch

    def setup_lut_discharging(self):
        # calculate power for corners of lut
        pow_min_dch = []
        pow_min_dch += [self.model.get_power(self.model.m_min_discharge, self.model.p_min, 'discharging')[1]]
        pow_min_dch += [self.model.get_power(self.model.m_min_discharge, self.model.p_max, 'discharging')[1]]
        pow_max_dch = []
        pow_max_dch += [self.model.get_power(self.model.m_max_discharge, self.model.p_min, 'discharging')[1]]
        pow_max_dch += [self.model.get_power(self.model.m_max_discharge, self.model.p_max, 'discharging')[1]]

        # change model to lut
        self.model.method = 'lut'
        self.model.load_lut_model()

        return pow_min_dch, pow_max_dch

    def test_tespy_charging_mass_flow(self):
        # mass flow in offdesign same as design mass flow?
        m_calc = round(self.model.get_mass_flow(self.model.power_nominal_charge, self.model.pressure_nominal_charge, 'charging')[0], 5)
        m_precalc = round(self.model.tespy_charge.imp_conns[self.model.massflow_conn_charge].m.design, 5)
        eq_(m_calc, m_precalc)

        # power throttling
        m_calc = round(self.model.get_mass_flow(self.model.power_nominal_charge * 2, self.model.pressure_nominal_charge, 'charging')[0], 5)
        m_precalc = round(self.model.m_max_charge, 5)
        eq_(m_calc, m_precalc)

        # power plant shut down
        m_calc = self.model.get_mass_flow(self.model.power_nominal_charge / 10, self.model.pressure_nominal_charge, 'charging')[0]
        m_precalc = 0
        eq_(m_calc, m_precalc)

    def test_tespy_discharging_mass_flow(self):
        # discharging
        # mass flow in offdesign same as design mass flow?
        m_calc = round(self.model.get_mass_flow(self.model.power_nominal_discharge, self.model.pressure_nominal_discharge, 'discharging')[0], 5)
        m_precalc = round(self.model.tespy_discharge.imp_conns[self.model.massflow_conn_discharge].m.design, 5)
        eq_(m_calc, m_precalc)

        # power throttling
        m_calc = round(self.model.get_mass_flow(self.model.power_nominal_discharge * 2, self.model.pressure_nominal_discharge, 'discharging')[0], 5)
        m_precalc = round(self.model.m_max_discharge, 5)
        eq_(m_calc, m_precalc)

        # power plant shut down
        m_calc = round(self.model.get_mass_flow(self.model.power_nominal_discharge / 10, self.model.pressure_nominal_discharge, 'discharging')[0], 5)
        m_precalc = 0
        eq_(m_calc, m_precalc)

    def test_tespy_pressure_limits(self):
        # out of pressure limits
        # lower limit
        power_does_not_matter_either = 999999
        m_calc = round(self.model.get_mass_flow(power_does_not_matter_either, self.model.p_min - 1, 'does not matter')[0], 5)
        m_precalc = 0
        eq_(m_calc, m_precalc)

        # upper limit
        m_calc = round(self.model.get_mass_flow(power_does_not_matter_either, self.model.p_max + 1, 'does not matter')[0], 5)
        m_precalc = 0
        eq_(m_calc, m_precalc)

    def test_lut_charging_mass_flow(self):
        pow_min_ch, pow_max_ch = self.setup_lut_charging()

        # as design point is not necessarily part of tabular data, edges are checked
        # minimum mass flow at minimum pressure
        m_calc = round(self.model.get_mass_flow(pow_min_ch[0], self.model.p_min, 'charging')[0], 5)
        m_precalc = round(self.model.m_min_charge, 5)
        eq_(m_calc, m_precalc)
        # minimum mass flow at maximum pressure
        m_calc = round(self.model.get_mass_flow(pow_min_ch[1], self.model.p_max, 'charging')[0], 5)
        m_precalc = round(self.model.m_min_charge, 5)
        eq_(m_calc, m_precalc)
        # maximum mass flow at minimum pressure
        m_calc = round(self.model.get_mass_flow(pow_max_ch[0], self.model.p_min, 'charging')[0], 5)
        m_precalc = round(self.model.m_max_charge, 5)
        eq_(m_calc, m_precalc)
        # maximum mass flow at maximum pressure
        m_calc = round(self.model.get_mass_flow(pow_max_ch[1], self.model.p_max, 'charging')[0], 5)
        m_precalc = round(self.model.m_max_charge, 5)
        eq_(m_calc, m_precalc)

        # power throttling
        m_calc = round(self.model.get_mass_flow(pow_max_ch[1] * 1.5, self.model.p_max, 'charging')[0], 5)
        m_precalc = round(self.model.m_max_charge, 5)
        eq_(m_calc, m_precalc)

        # power plant shut down
        m_calc = self.model.get_mass_flow(pow_min_ch[1] / 5, self.model.p_max, 'charging')[0]
        m_precalc = 0
        eq_(m_calc, m_precalc)

    def test_lut_charging_power(self):
        pow_min_ch, pow_max_ch = self.setup_lut_charging()

        # calculate power from mass flow
        # minimum mass flow and minimum pressure
        pow_calc = round(self.model.get_power(self.model.m_min_charge, self.model.p_min, 'charging')[1], 5)
        pow_precalc = round(pow_min_ch[0], 5)
        eq_(pow_calc, pow_precalc)

        # minimum mass flow and maximum pressure
        pow_calc = round(self.model.get_power(self.model.m_min_charge, self.model.p_max, 'charging')[1], 5)
        pow_precalc = round(pow_min_ch[1], 5)
        eq_(pow_calc, pow_precalc)

        # maximum mass flow and minimum pressure
        pow_calc = round(self.model.get_power(self.model.m_max_charge, self.model.p_min, 'charging')[1], 5)
        pow_precalc = round(pow_max_ch[0], 5)
        eq_(pow_calc, pow_precalc)

        # maximum mass flow and maximum pressure
        pow_calc = round(self.model.get_power(self.model.m_max_charge, self.model.p_max, 'charging')[1], 5)
        pow_precalc = round(pow_max_ch[1], 5)
        eq_(pow_calc, pow_precalc)

    def test_lut_discharging_mass_flow(self):
        pow_min_dch, pow_max_dch = self.setup_lut_discharging()

        # as design point is not necessarily part of tabular data, edges are checked
        # minimum mass flow at minimum pressure
        m_calc = round(self.model.get_mass_flow(pow_min_dch[0], self.model.p_min, 'discharging')[0], 5)
        m_precalc = round(self.model.m_min_discharge, 5)
        eq_(m_calc, m_precalc)
        # minimum mass flow at maximum pressure
        m_calc = round(self.model.get_mass_flow(pow_min_dch[1], self.model.p_max, 'discharging')[0], 5)
        m_precalc = round(self.model.m_min_discharge, 5)
        eq_(m_calc, m_precalc)
        # maximum mass flow at minimum pressure
        m_calc = round(self.model.get_mass_flow(pow_max_dch[0], self.model.p_min, 'discharging')[0], 5)
        m_precalc = round(self.model.m_max_discharge, 5)
        eq_(m_calc, m_precalc)
        # maximum mass flow at maximum pressure
        m_calc = round(self.model.get_mass_flow(pow_max_dch[1], self.model.p_max, 'discharging')[0], 5)
        m_precalc = round(self.model.m_max_discharge, 5)
        eq_(m_calc, m_precalc)

        # power throttling
        m_calc = round(self.model.get_mass_flow(pow_max_dch[1] * 1.5, self.model.p_max, 'discharging')[0], 5)
        m_precalc = round(self.model.m_max_discharge, 5)
        eq_(m_calc, m_precalc)

        # power plant shut down
        m_calc = self.model.get_mass_flow(pow_min_dch[1] / 5, self.model.p_max, 'discharging')[0]
        m_precalc = 0
        eq_(m_calc, m_precalc)

    def test_lut_discharging_power(self):
        pow_min_dch, pow_max_dch = self.setup_lut_discharging()

        # calculate power from mass flow
        # minimum mass flow and minimum pressure
        pow_calc = round(self.model.get_power(self.model.m_min_discharge, self.model.p_min, 'discharging')[1], 5)
        pow_precalc = round(pow_min_dch[0], 5)
        eq_(pow_calc, pow_precalc)

        # minimum mass flow and maximum pressure
        pow_calc = round(self.model.get_power(self.model.m_min_discharge, self.model.p_max, 'discharging')[1], 5)
        pow_precalc = round(pow_min_dch[1], 5)
        eq_(pow_calc, pow_precalc)

        # maximum mass flow and minimum pressure
        pow_calc = round(self.model.get_power(self.model.m_max_discharge, self.model.p_min, 'discharging')[1], 5)
        pow_precalc = round(pow_max_dch[0], 5)
        eq_(pow_calc, pow_precalc)

        # maximum mass flow and maximum pressure
        pow_calc = round(self.model.get_power(self.model.m_max_discharge, self.model.p_max, 'discharging')[1], 5)
        pow_precalc = round(pow_max_dch[1], 5)
        eq_(pow_calc, pow_precalc)
