#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 12 15:17:46 2018

__author__ = "witte, wtp"

"""

import sys
import getopt
import pandas as pd
import numpy as np
from coupled_simulation import powerplant as pp, geostorage as gs
import json
import datetime
import os

def __main__(argv):
    """
    main function to initialise the calculation

    - creates power plant and storage models
    - reads input timeseries
    - starts the loop
    - writes results to .csv-file

    :param md: object containing the basic model data
    :type md: model_data object
    :returns: no return value
    """

    if len(argv) == 0:
        return

    #read main input file and set control variables, e.g. paths, identifiers, ...
    #path = (r'D:\Simulations\if_testcase\testcase.main_ctrl.json')
    path = ''

    try:
        opts, args = getopt.getopt(argv,"hi:o:",["ipath="])
    except getopt.GetoptError:
        print('test.py -i <inputpath>')
        sys.exit(2)
    print(opts)
    print(argv)
    for opt, arg in opts:
        if opt == '-h':
            print('test.py -i <inputpath>')
            sys.exit()
        elif opt in ("-i", "--ipath"):
            path = arg

    print(path)

    if path[0] == "r":
        path = path[1:]

    path_log = path[:-15]
    path_log += ".log"
    #check if file exists and delete if necessary
    if os.path.isfile(path_log):
        os.remove(path_log)
    #save screen output in file
    sys.stdout = Logger(path_log)

    print('Input file is:')
    print(path)

    print('################################################################################################################')
    print('Assembling model data...')

    cd = coupling_data(path=path)

    # create instances for power plant and storage
    geostorage = gs.geo_sto(cd)

    min_well_depth = min(geostorage.well_depths)
    #min_well_depth = 700 #read this from file later!

    powerplant = pp.model(cd, min_well_depth, len(geostorage.well_names), max(geostorage.well_upper_BHP), min(geostorage.well_lower_BHP))
    #powerplant = pp.model(cd, min_well_depth, 9, 80, 40)

    print('################################################################################################################')
    print('Reading input time series...')

    input_ts = read_series(cd.working_dir + cd.input_timeseries_path)

    #prepare data structures
    print('################################################################################################################')
    print('Preparing output data structures...')
    variable_list = []
    if cd.auto_eval_output == True:
        variable_list = ['time', 'power_target', 'massflow_target', 'power_actual', 'heat', 'massflow_actual','storage_pressure', 'Tstep_accepted', 'delta_power', 'delta_massflow' ]
    else:
        variable_list = ['time', 'power_target', 'massflow_target', 'power_actual', 'heat', 'massflow_actual', 'storage_pressure' ]
    #one output line per timestep...
    output_ts = pd.DataFrame(index=np.arange(0, cd.t_steps_total),columns=variable_list)

    #print(output_ts)
    '''debug values from here onwards'''
    #data = [0.0, 0.0]
    #data = geostorage.CallStorageSimulation(1.15741, 1, cd, 'charging')
    #data = geostorage.CallStorageSimulation(0.0, 2, cd, 'shut-in')
    #data = geostorage.CallStorageSimulation(-1.15741, 3, cd, 'discharging')
    '''end of debug values'''

    print('################################################################################################################')
    p0 = 0.0 #old pressure (from last time step / iter)
    # get initial pressure before the time loop
    p0, dummy_flow = geostorage.CallStorageSimulation(0.0, -1, 0, cd, 'init')
    print('Simulation initialzation completed.')
    print('################################################################################################################')

    # to shut of power plant until pressure is acceptable again
    power_plant_off = False
    power_target_t0 = 0.0
    power_target = 0.0

    last_time = cd.t_start
    for t_step in range(cd.t_steps_total):

        current_time = datetime.timedelta(seconds=t_step * cd.t_step_length) + cd.t_start



        try:
            power_target = input_ts.loc[current_time].power * 1e6
            last_time = current_time
        except KeyError:
            power_target = input_ts.loc[last_time].power * 1e6

        print('################################################################################################################')
        print('################################################################################################################')
        print('################################################################################################################')

        print('Advancing to timestep:\t', t_step)
        print('Target power output for this time step is: ','%.3f'%power_target)
        sys.stdout.flush()

        if power_plant_off == True:
            print ( 'Power plant was shut down last time step. Tracking changes in storage mode')
            print ( 'Target power last time step: ', power_target_t0)
            print ( 'Target power current time step: ', power_target)
            if abs(power_target - power_target_t0) > 1E-7:
                print ( 'Attempting to restart power plant')
                power_plant_off = False

        # calculate pressure, mass flow and power
        p_actual, m_target, m_actual, power_actual, heat, success, power_plant_off = calc_timestep(
                powerplant, geostorage, power_target, p0, cd, t_step, power_plant_off)

        # save last pressure (p1) for next time step as p0
        p0 = p_actual
        #deleting old files
        geostorage.deleteSimFiles(t_step)

        # write pressure, mass flow and power to .csv
        if cd.auto_eval_output == True:
            delta_power = abs(power_actual) - abs(power_target)
            delta_massflow = abs(m_actual) - abs(m_target)

            output_ts.loc[t_step] = np.array([current_time, power_target, m_target, power_actual, heat, m_actual,
                                                    p_actual, success, delta_power, delta_massflow])
        else:
            output_ts.loc[t_step] = np.array([current_time, power_target, m_target, power_actual, heat, m_actual,
                                                    p_actual])

        #Logger.flush()

        #sys.stdout.flush() #force flush of output

        #if t_step % cd.save_nth_t_step == 0:
        output_ts.to_csv(cd.working_dir + cd.output_timeseries_path, index=False, sep=';')

        #save old power target
        power_target_t0 = power_target

    if balance_mass_eos:

        accumulated_mass = output_ts['massflow_actual'].cumsum()

        if accumulated_mass > 0:
            mode = 'discharging'
            time = (abs(accumulated_mass) / powerplant.m_nom_discharge) // 3600 + 1
            massflow_target = -powerplant.m_nom_discharge
        elif accumulated_mass < 0:
            mode = 'charging'
            time = (abs(accumulated_mass) / powerplant.m_nom_charge) // 3600 + 1
            massflow_target = powerplant.m_nom_charge
        else:
            time = 0

        for t_step in range(time):
            # calculate pressure, mass flow and power
            p_actual, m_target, m_actual, power_actual, heat, success, power_plant_off = calc_timestep_mass(
                powerplant, geostorage, massflow_target, p0, cd, t_step, power_plant_off)


def calc_timestep_mass(powerplant, geostorage, massflow, p0, md, tstep, pp_off):
    """
    calculates one timestep of coupled power plant - storage simulation

    :param powerplant: powerplant model
    :type powerplant: powerplant.model object
    :param storage: storage model
    :type storage: storage.model object
    :param massflow: scheduled massflow for timestep
    :type power: float
    :param p0: initual pressure at timestep
    :type p0: float
    :param md: object containing the basic model data
    :type md: model_data object
    :returns: - p1 (*float*) - interface pressure at the end of the timestep
              - m_corr (*float*) - mass flow for this timestep
              - power (*float*) - power plant's input/output power for this
                timestep
    """
    tstep_accepted = False
    storage_mode = ''
    #setting inital pressure
    p1 = p0

    #initilizing variables
    power_corr = power
    m = massflow
    heat = 0.0
    p_delta_limit = 0.0
    p_limit = 0.0

    delta_m_iter = 0.0
    delta_m_iter_rel = 0.0
    delta_p_iter = 0.0
    delta_p_iter_rel = 0.0

    if massflow == 0.0: #matching float values, potentionally dangerous
        m = 0.0
        storage_mode = 'shut-in'
    elif massflow < 0.0:
        storage_mode = 'discharging'
    else:
        storage_mode = 'charging'

    print('Operational mode of the system is is: ', storage_mode)
    sys.stdout.flush()


    #moved inner iteration into timestep function,
    #iterate until timestep is accepted
    p0_temp = p0

    for iter_step in range(md.max_iter): #do time-specific iterations

        if tstep_accepted:
            print('Message: Timestep accepted after iteration ', iter_step - 1)
            break
        print('----------------------------------------------------------------------------------------------------------------')
        print('----------------------------------------------------------------------------------------------------------------')
        print('Current iteration:\t', iter_step)
        print('----------------------------------------------------------------------------------------------------------------')
        sys.stdout.flush()

        if pp_off == True:
            print('Power plant temporarily shut-off due to storage pressure. Mode set to shut-in')
            storage_mode = "shut-in"
            m = 0.0
            power_corr = 0.0
            sys.stdout.flush()
        else:
            #run power plant model to get target flow rate
            print('Running power plant model')
            m, power_corr, heat = powerplant.get_power(abs(m), p1, storage_mode)

        #if target mass flow is zero, set storage mode to shut-in
        if m == 0.0:    #matching float values, potentionally dangerous
            storage_mode = 'shut-in'
            power_corr = 0.0
        print('----------------------------------------------------------------------------------------------------------------')

        #get pressure for the given target rate and the actually achieved flow rate from storage simulation
        p1, m_corr = geostorage.CallStorageSimulation(m, tstep, iter_step, md, storage_mode)

        #evalute pressure difference
        delta_p_iter = abs(p1 - p0_temp)
        delta_p_iter_rel = delta_p_iter / p1

        if storage_mode == 'charging' or storage_mode == 'discharging':
            #evaluate flow rate difference
            if pp_off == False:
                delta_m_iter = abs(m_corr - m)
                delta_m_iter_rel = delta_m_iter / m_corr
            else:
                delta_m_iter = 0.0
                delta_m_iter_rel = 0.0

        if pp_off == True:
            print ('Power plant shut-off, testing pressure difference...')
            #determine pressure limit
            diff_to_max = abs(p1 - min(geostorage.well_upper_BHP))
            diff_to_min = abs(p1 - max(geostorage.well_lower_BHP))
            if diff_to_min < diff_to_max:
                #lower pressure
                p_limit = max(geostorage.well_lower_BHP)
            else:
                #upper pressure
                p_limit = min(geostorage.well_upper_BHP)
            p_delta_limit = abs(p1 - p_limit)
            print ('Pressure diff to limit is ', p_delta_limit , ' bars' )

            if p_delta_limit >= md.pressure_change_restart:
                print ('...restarting power plant.' )
                pp_off = False

            sys.stdout.flush()
        print('Summary of iteration:')
        print('m_target / m_storage\t\t', '%.6f'%m, '/', '%.6f'%m_corr, '[kg/s]')
        print('p_assumed / p_storage\t\t', '%.6f'%p0_temp, '/', '%.6f'%p1, '[bars]')

        if storage_mode == 'charging' or storage_mode == 'discharging':
            # pressure check
            if delta_p_iter_rel > md.pressure_diff_rel or delta_p_iter > md.pressure_diff_abs:
                print('Adjusting mass flow rate due to storage pressure difference.')
                m, power_corr, heat = powerplant.get_power(m, p1, storage_mode)
                if m == 0:
                    print('Forcing shut-in mode as m is zero.')
                    storage_mode = 'shut-in'
                sys.stdout.flush()

            elif delta_m_iter_rel > md.flow_diff_rel or delta_m_iter > md.flow_diff_abs:
                print('Storage pressure converged and mass flow is not...')
                m, power_corr, heat = powerplant.get_power(m_corr, p1, storage_mode)
                m = m_corr
                print('Adjusting power to ', power_corr)
                if power_corr == 0.0:
                    print ('Power plant shut off due min. mass flow violation: Storage shut-in')
                    storage_mode = 'shut-in'
                    pp_off = True
                    m = 0.0
                else:
                    tstep_accepted = True
                    #update storage pressure, required as tstep is accepted and loop is terminated
                    #p1, m_corr = geostorage.CallStorageSimulation(m, tstep, iter_step, md, storage_mode )
                sys.stdout.flush()

            else:
                print('Storage pressure and mass flow converged.')
                #return p1, m_corr, power
                tstep_accepted = True
                #m = m_corr

            if storage_mode == 'charging':
                if m < powerplant.m_max_charge and p1 < p0_temp:
                    print ('current target mass flow is: ', '%.6f'%m, '[kg/s]')
                    print ('current pressure is: ', '%.6f'%p1, '[bar]')
                    print ('last pressure was: ', '%.6f'%p0_temp, '[bar]')
                    print ('updating target mass output during charging to time step target')
                    m = m_corr
            elif storage_mode == 'discharging':
                if m < powerplant.m_max_discharge and p1 > p0_temp:
                    print ('current target mass flow is: ', '%.6f'%m, '[kg/s]')
                    print ('current pressure is: ', '%.6f'%p1, '[bar]')
                    print ('last pressure was: ', '%.6f'%p0_temp, '[bar]')
                    print ('Updating target mass output during discharging to time step target')
                    m = m_corr

        elif storage_mode == "shut-in":
            print('Force accepting timestep b/c storage shut-in')
            tstep_accepted = True
        else:
            print('Problem: Storage mode not understood')
            tstep_accepted = True

        #saving old pressure
        p0_temp = p1

    if not tstep_accepted:
        print('----------------------------------------------------------------------------------------------------------------')
        print('----------------------------------------------------------------------------------------------------------------')
        print('Problem: Results in timestep ', tstep, 'did not converge, accepting last iteration result.')
    sys.stdout.flush()
    return p1, m, m_corr, power_corr, heat, tstep_accepted, pp_off


def calc_timestep(powerplant, geostorage, power, p0, md, tstep, pp_off):
    """
    calculates one timestep of coupled power plant - storage simulation

    :param powerplant: powerplant model
    :type powerplant: powerplant.model object
    :param storage: storage model
    :type storage: storage.model object
    :param power: scheduled power for timestep
    :type power: float
    :param p0: initual pressure at timestep
    :type p0: float
    :param md: object containing the basic model data
    :type md: model_data object
    :returns: - p1 (*float*) - interface pressure at the end of the timestep
              - m_corr (*float*) - mass flow for this timestep
              - power (*float*) - power plant's input/output power for this
                timestep
    """
    tstep_accepted = False
    storage_mode = ''
    #setting inital pressure
    p1 = p0

    #initilizing variables
    target_power_tstep = power
    power_corr = power
    heat = 0.0
    p_delta_limit = 0.0
    p_limit = 0.0

    delta_m_iter = 0.0
    delta_m_iter_rel = 0.0
    delta_p_iter = 0.0
    delta_p_iter_rel = 0.0

    if power == 0.0: #matching float values, potentionally dangerous
        m = 0.0
        storage_mode = 'shut-in'
    elif power < 0.0:
        storage_mode = 'discharging'
        #m, power_corr = powerplant.get_mass_flow(power, p0, storage_mode)
    else:
        storage_mode = 'charging'
        #m, power_corr = powerplant.get_mass_flow(power, p0, storage_mode)

    print('Operational mode of the system is is: ', storage_mode)
    sys.stdout.flush()


    #moved inner iteration into timestep function,
    #iterate until timestep is accepted
    p0_temp = p0

    for iter_step in range(md.max_iter): #do time-specific iterations

        if tstep_accepted:
            print('Message: Timestep accepted after iteration ', iter_step - 1)
            break
        print('----------------------------------------------------------------------------------------------------------------')
        print('----------------------------------------------------------------------------------------------------------------')
        print('Current iteration:\t', iter_step)
        print('----------------------------------------------------------------------------------------------------------------')
        sys.stdout.flush()

        if pp_off == True:
            print ('Power plant temporarily shut-off due to storage pressure. Mode set to shut-in')
            storage_mode = "shut-in"
            m = 0.0
            power_corr = 0.0
            sys.stdout.flush()
        else:
            #run power plant model to get target flow rate
            print ('Running power plant model')
            m, power_corr, heat = powerplant.get_mass_flow(power, p1, storage_mode)

        #if target mass flow is zero, set storage mode to shut-in
        if m == 0.0:    #matching float values, potentionally dangerous
            storage_mode = 'shut-in'
            power_corr = 0.0
        print('----------------------------------------------------------------------------------------------------------------')

        #get pressure for the given target rate and the actually achieved flow rate from storage simulation
        p1, m_corr = geostorage.CallStorageSimulation(m, tstep, iter_step, md, storage_mode )

        #evalute pressure difference
        delta_p_iter = abs(p1 - p0_temp)
        delta_p_iter_rel = delta_p_iter / p1

        if storage_mode == 'charging' or storage_mode == 'discharging':
            #evaluate flow rate difference
            if pp_off == False:
                delta_m_iter = abs(m_corr - m)
                delta_m_iter_rel = delta_m_iter / m_corr
            else:
                delta_m_iter = 0.0
                delta_m_iter_rel = 0.0

        if pp_off == True:
            print ('Power plant shut-off, testing pressure difference...')
            #determine pressure limit
            diff_to_max = abs(p1 - min(geostorage.well_upper_BHP))
            diff_to_min = abs(p1 - max(geostorage.well_lower_BHP))
            if diff_to_min < diff_to_max:
                #lower pressure
                p_limit = max(geostorage.well_lower_BHP)
            else:
                #upper pressure
                p_limit = min(geostorage.well_upper_BHP)
            p_delta_limit = abs(p1 - p_limit)
            print ('Pressure diff to limit is ', p_delta_limit , ' bars' )

            if p_delta_limit >= md.pressure_change_restart:
                print ('...restarting power plant.' )
                pp_off = False

            sys.stdout.flush()
        print( 'Summary of iteration:')
        print('m_target / m_storage\t\t', '%.6f'%m, '/', '%.6f'%m_corr, '[kg/s]')
        print('p_assumed / p_storage\t\t', '%.6f'%p0_temp, '/', '%.6f'%p1, '[bars]')

        if storage_mode == 'charging' or storage_mode == 'discharging':
            # pressure check
            if delta_p_iter_rel > md.pressure_diff_rel or delta_p_iter > md.pressure_diff_abs:
                print('Adjusting mass flow rate due to storage pressure difference.')
                m, power_corr, heat = powerplant.get_mass_flow(power, p1, storage_mode)
                if m == 0:
                    print('Forcing shut-in mode as m is zero.')
                    storage_mode = 'shut-in'
                sys.stdout.flush()

            elif delta_m_iter_rel > md.flow_diff_rel or  delta_m_iter > md.flow_diff_abs:
                print('Storage pressure converged and mass flow is not...')
                m, power_corr, heat = powerplant.get_power(m_corr, p1, storage_mode)
                m = m_corr
                print('Adjusting power to ', power_corr)
                if power_corr == 0.0:
                    print ('Power plant shut off due min. mass flow violation: Storage shut-in')
                    storage_mode = 'shut-in'
                    pp_off = True
                    m = 0.0
                else:
                    tstep_accepted = True
                    #update storage pressure, required as tstep is accepted and loop is terminated
                    #p1, m_corr = geostorage.CallStorageSimulation(m, tstep, iter_step, md, storage_mode )
                sys.stdout.flush()

            else:
                print('Storage pressure and mass flow converged.')
                #return p1, m_corr, power
                tstep_accepted = True
                #m = m_corr

            if storage_mode == 'charging':
                if m < powerplant.m_max_charge and p1 < p0_temp:
                    print ('current target mass flow is: ', '%.6f'%m, '[kg/s]')
                    print ('current pressure is: ', '%.6f'%p1, '[bar]')
                    print ('last pressure was: ', '%.6f'%p0_temp, '[bar]')
                    print ('updating target power output during charging to time step target')
                    power = power_corr
            elif storage_mode == 'discharging':
                if m < powerplant.m_max_discharge and p1 > p0_temp:
                    print ('current target mass flow is: ', '%.6f'%m, '[kg/s]')
                    print ('current pressure is: ', '%.6f'%p1, '[bar]')
                    print ('last pressure was: ', '%.6f'%p0_temp, '[bar]')
                    print ('Updating target power output during discharging to time step target')
                    power = power_corr

        elif storage_mode == "shut-in":
            print('Force accepting timestep b/c storage shut-in')
            tstep_accepted = True
        else:
            print('Problem: Storage mode not understood')
            tstep_accepted = True

        #saving old pressure
        p0_temp = p1

    if not tstep_accepted:
        print('----------------------------------------------------------------------------------------------------------------')
        print('----------------------------------------------------------------------------------------------------------------')
        print('Problem: Results in timestep ', tstep, 'did not converge, accepting last iteration result.')
    sys.stdout.flush()
    return p1, m, m_corr, power_corr, heat, tstep_accepted, pp_off


def read_series(path):
    """
    reads the input time series

    :param path: path to input time series
    :type path: str
    :returns: ts (*pandas.DataFrame*) - dataframe containing the time series
    """
    ts = pd.read_csv(path, delimiter=';', decimal='.')
    ts = ts.set_index('timeindex')
    ts.index = pd.to_datetime(ts.index)
    ts['power'] = ts['input'] - ts['output']

    return ts


class coupling_data:
    """
    creates a data container with the main model parameters

    :returns: no return value
    """

    def __init__(self, path):

        # load data.json information into objects dictionary (= attributes of
        # the object)
        self.path = path

        with open(path) as f:
            self.__dict__.update(json.load(f))

        self.auto_eval_output = False

        if self.eval_output == "True":
            self.auto_eval_output = True

        self.coupled_simulation()

    def coupled_simulation(self):
        """
        Function to set all required default data, e.g. well names, paths, ...

        :returns: no return value
        """
        #print("path is: ", self.path)

        str_tmp = self.path[:-15]
        #print("str_tmp is: ", str_tmp)
        self.scenario = ""
        self.working_dir = ""

        i = 0
        key = ""
        if os.name == 'nt':
            key = "\\"
        elif os.name == 'posix':
            key = "/"
        else:
            print('Error: OS not supported')


        for c in str_tmp[::-1]:
            if c == key:
                self.working_dir = str_tmp[:-i]
                break
            self.scenario += c
            i += 1
        #print("Scenario is: ", self.scenario)

        self.scenario = self.scenario[::-1]
        #print("Scenario is now: ", self.scenario)

        self.debug = bool(self.debug)
        date_format = '%Y-%m-%d %H:%M:%S'
        self.t_start = datetime.datetime.strptime(self.t_start, date_format)

        print('Reading inputile \"' + self.scenario + '.main_ctrl.json\" ')
        print('in working directory \"' + self.working_dir + '\"')

'''        if self.debug:
            print('DEBUG-OUTPUT for main control data')
            print('Time series path:\t' + self.input_timeseries_path)
            print('Start time:\t' + str(self.t_start))
            print('Time step length:\t' + str(self.t_step_length))
            print('Number of time steps:\t' + str(self.t_steps_total))
            print('Iteration limits:\t' + str(self.min_iter) + '\t' +
                  str(self.max_iter))
            print('Pressure convergence criteria:\t' +
                  str(self.pressure_diff_abs) +
                  ' bars\t' + str(self.pressure_diff_rel * 100) + ' %')
            print('END of DEBUG-OUTPUT for main control data')'''

class Logger(object):

    def __init__(self, a_string):
        self.terminal = sys.stdout
        self.log = open(a_string, "a")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)

    def flush(self):
        #this flush method is needed for python 3 compatibility.
        #this handles the flush command by doing nothing.
        #you might want to specify some extra behavior here.
        pass

__main__(sys.argv[1:])
