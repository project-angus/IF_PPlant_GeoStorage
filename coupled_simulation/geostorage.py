#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""

__author__ = "wtp, fgasa"

"""

from coupled_simulation import utilities as util
import json
import os
import re
import subprocess

class GeoStorage:

    '''
    Class to include geologic storage simulations.

    Translates target mass flow commands into simulator-specific inputs, executes
    the simulation for a single timestep, and extracts the resulting reservoir state.

    Returns: tuple: (pressure_actual, flowrate_actual) as standardized floats.

    '''
    def __init__(self, cd):

        # load data.json information into objects dictionary (= attributes of
        # the object)
        geostorage_path = cd.geostorage_path.replace('\\', os.sep).strip(os.sep)
        wdir = os.path.join(cd.working_dir, geostorage_path)
        path = os.path.join(wdir, f"{cd.scenario}.geostorage_ctrl.json")
        with open(path) as f:
            self.__dict__.update(json.load(f))

        self.working_dir_loc = wdir
        self.keep_ecl_logs = False

        # save the original simulation title in case of eclipse simulation (not needed for e300)
        self.simulation_title_orig = self.simulation_title
        self.current_simulation_title = self.simulation_title
        self.old_simulation_title = self.simulation_title

        if self.retain_ecl_logs == "True":
            self.keep_ecl_logs = True
        else:
            self.keep_ecl_logs = False

    def call_storage_simulation(self, target_flow, tstep, iter_step, coupling_data, op_mode):
        '''
        Entry point for geo-storage simulation, handles all data transfer, executes simulator
        and provides simulation results to power plant simulator

        :param target_flow: target storage flow rate in sm3/d; 15.5556°C, 1 atm
        :param type: float
        :param tstep: current timestep
        :param type: int
        :param tstepsize: length of current timestep
        :param type: float
        :param op_mode: current operational mode, either 'charging', 'discharging' or 'shut-in'
        :param type: str
        :returns: returns tuple of new pressure at the well (in reservoir) and actual (achieved) storage flow rate
        '''
        #this is the entry point for the geostorage coupling

        if self.simulator in ['ECLIPSE', 'e300']:
            flowrate, pressure = self.run_simulator(target_flow, tstep, iter_step, coupling_data.t_step_length, op_mode)
        elif self.simulator == 'PROXY':
            flowrate, pressure = self.run_proxy(target_flow, tstep, iter_step, coupling_data.t_step_length, op_mode)
        elif self.simulator == 'OPM':
            flowrate, pressure = self.run_simulator(target_flow, tstep, iter_step, coupling_data.t_step_length, op_mode)
        else:
            print('ERROR: simulator flag not understood. Is: ', self.simulator)

        return pressure, flowrate

    def run_simulator(self, target_flowrate, tstep, iter_step, tstepsize, current_mode):
        '''
        Function acting as a wrapper for using eclipse (SChlumberger) as a storage simulator

        :param target_flowrate: target storage flow rate in sm3/d; 15.5556°C, 1 atm
        :param type: float
        :param tstep: current timestep
        :param type: int
        :param tstepsize: length of current timestep
        :param type: float
        :param op_mode: current operational mode, either 'charging', 'discharging' or 'shut-in'
        :param type: str
        :returns: returns tuple of new pressure at the well (in reservoir) and actual (achieved) storage flow rate
        '''

        #set simulation title
        if iter_step == 0:
            #print ( 'iteration: keeping title')
            self.old_simulation_title = self.current_simulation_title

        if current_mode == 'init':
            self.current_simulation_title = self.simulation_title_orig + '_TSTEP_INIT'
            os.rename(
                os.path.join(self.working_dir_loc, f"{self.simulation_title_orig}.DATA"),
                os.path.join(self.working_dir_loc, f"{self.current_simulation_title}.DATA")
            )
        else:
            if iter_step == 0:
                self.current_simulation_title = self.simulation_title_orig + '_TSTEP_' + str(tstep)
                os.rename(
                    os.path.join(self.working_dir_loc, f"{self.old_simulation_title}.DATA"),
                    os.path.join(self.working_dir_loc, f"{self.current_simulation_title}.DATA")
                )

        if not current_mode == 'init':
            print(f"{'Running storage simulation'}")
            print(f"{'Simulation title:':30s} {self.current_simulation_title}")
            print(f"{'Timestep / iteration:':30s} {int(tstep)} / {int(iter_step)}")
            print(f"{'Timestep size [s]:':30s} {tstepsize:.0f}")
            print(f"{'Target flowrate [kg/s]:':30s} {target_flowrate:.6f}")  # storage flow rate
            print(f"{'Target flowrate [sm3/s]:':30s} {(target_flowrate / self.surface_density):.6f}")
            print(f"{'Operational mode:':30s} {current_mode}")

        else:
            print('Running storage simulation to obtain initial pressure')

        #adjusting to surface volume rates
        target_flowrate = target_flowrate / self.surface_density

        # assembling current ecl data file
        self.rework_ecl_data(tstep, tstepsize, target_flowrate, current_mode)
        # executing reservoir simulator
        if str(self.simulator).upper().startswith("OPM"):
            self.execute_opm(tstep, iter_step)
        else:
            self.execute_ecl(tstep, iter_step, current_mode)
        # reading results
        ecl_results = self.get_ecl_results(tstep, current_mode)

        #adjusting to mass flow rates
        ecl_results[1] = ecl_results[1] * self.surface_density

        if not current_mode == 'init':
            print("-" * 50)
            print(f"{'Pressure actual [bar]:':30s} {'%.6f' % ecl_results[0]}")
            print(f"{'Flowrate actual [kg/s]:':30s} {'%.6f' % ecl_results[1]}")
            print(f"{' ':30s} {'%.6f' % (ecl_results[1] / self.surface_density)}" ' [sm3/s]')
        else:
            print(f"{'Initial pressure is: '} {'%.6f' % ecl_results[0]}" ' [bar]')
        print("-" * 50)
        return (ecl_results[1], ecl_results[0])

    def rearrange_rsm_data_array(self, rsm_list):
        '''
        Function to sort through Eclipse's RSM file and obtain well data from last timestep

        :param rsm_list: list containing the RSM file
        :param type: str
        :returns: returns a clearer version of the input list (type: list of strings)
        '''
        # function to re-order / get rid off line breaks etc. in input
        #break_count = util.getStringCount(rsm_list, 'SUMMARY OF RUN')

        break_positions = util.get_string_positions(rsm_list, 'SUMMARY OF RUN')
        break_count = len(break_positions)

        if break_count > 0:
            interval = break_positions[1] - break_positions[0]

        output = []

        for i in range(break_count):
            for j in range(interval):
                current_idx = i * interval + j
                if i == 0:
                    temp = rsm_list[current_idx][:-3]
                    output.append(rsm_list[i])
                if j > 1:
                    #print('current_idx: ', current_idx)
                    temp1 = str(output[j]).replace('\n', '')
                    temp1 = temp1[:-3]
                    temp2 = str(rsm_list[current_idx])
                    temp2 = temp2[:-3]
                    temp2 += '\n'
                    temp = temp1 + temp2
                    temp = temp.replace('\t\t', '\t')

                    output[j] = temp
        #delete first two (empty) entries
        del output[0]
        del output[0]

        return output

    def rearrange_rsm_data_array_opm(self, rsm_lines):
        """
        Function to parse OPM  .RSM output with multiple 'SUMMARY OF RUN' blocks per timestep.
        OPM writes multiple 'SUMMARY OF RUN' blocks, each with up to ~10 columns. Each block has 5 rows.
        Return two strings (header_line, data_line) separated by tabs so downstream
        """
        date_regex = re.compile(r'\d{1,2}-[A-Z]{3}-\d{4}', re.IGNORECASE)
        n = len(rsm_lines)
        i = 0
        blocks = []
        tab_size = 16  # standard width for output?

        # Walk lines and capture blocks starting at header "DATE ..."
        while i < n:
            line = rsm_lines[i]
            if line.strip().startswith('DATE'):
                header_line = line.expandtabs(tab_size).rstrip('\n')
                unit_line = rsm_lines[i + 1].expandtabs(tab_size).rstrip('\n') if i + 1 < n else ''
                well_line = rsm_lines[i + 2].expandtabs(tab_size).rstrip('\n') if i + 2 < n else ''
                # find first data line after the header chunk (line that matches date pattern)
                j = i + 3
                data_line = None
                while j < n:
                    if date_regex.search(rsm_lines[j]):
                        data_line = rsm_lines[j].expandtabs(tab_size).rstrip('\n')
                        break
                    j += 1

                if data_line is not None:
                    blocks.append((header_line, unit_line, well_line, data_line))
                    i = j + 1
                    continue
            i += 1

        all_headers = []
        all_units = []
        all_wells = []
        all_data = []
        date_value = 'n.a.'

        # map data based on physical character alignment
        for (hdr, unit, wells, data) in blocks:
            # normalize and split on two-or-more spaces to keep column groups
            h_matches = list(re.finditer(r'\S+', hdr))
            if not h_matches:
                continue

            def get_closest_idx(match_obj):
                center = (match_obj.start() + match_obj.end()) / 2
                best_idx = 0
                min_dist = float('inf')
                for idx, h_m in enumerate(h_matches):
                    h_center = (h_m.start() + h_m.end()) / 2
                    if abs(center - h_center) < min_dist:
                        min_dist = abs(center - h_center)
                        best_idx = idx
                return best_idx

            block_headers = [m.group() for m in h_matches]
            block_units = ['-'] * len(block_headers)
            block_wells = ['-'] * len(block_headers)
            block_data = ['0.0'] * len(block_headers)

            for m in re.finditer(r'\S+', unit):
                block_units[get_closest_idx(m)] = m.group()
            for m in re.finditer(r'\S+', wells):
                block_wells[get_closest_idx(m)] = m.group()
            for m in re.finditer(r'\S+', data):
                val = m.group()
                block_data[get_closest_idx(m)] = val
                if date_regex.match(val) and date_value == 'n.a.':
                    date_value = val

            # append to master lists, skipping redundant 'DATE' columns
            for idx, h_var in enumerate(block_headers):
                if h_var.upper() == 'DATE' and len(all_headers) > 0:
                    continue
                all_headers.append(h_var)
                all_units.append(block_units[idx])
                all_wells.append(block_wells[idx])
                all_data.append(block_data[idx])

        if all_data and date_value != 'n.a.':
            all_data[0] = date_value

        return ['\t'.join(all_headers) + '\n',
                '\t'.join(all_units) + '\n',
                '\t'.join(all_wells) + '\n',
                '\t'.join(all_data) + '\n']

    def rework_ecl_data(self, timestep, timestepsize, flowrate, op_mode):
        '''
        function to change settings in the eclipse input file required for the storage simulation

        :param timestep: current timestep of simulation
        :param type: int
        :param timestepsize: length of current timestep
        :param type: float
        :param flowrate: current target storage flow rate from power plant simulation
        :param type: float
        :param op_mode: current operational mode, either 'charging', 'discharging' or 'shut-in'
        :param type: str
        :returns: no return value
        '''
        # open and read eclipse data file
        ecl_data_file = util.get_file(os.path.join(self.working_dir_loc, self.current_simulation_title + '.DATA'))
        #print(self.working_dir_loc + self.simulation_title + '.DATA')
        #print ('rework ecl data tstep:', timestep)
        #rearrange the entries in the saved list
        if timestep == 1:
            #look for EQUIL and RESTART keyword
            equil_pos = util.search_section(ecl_data_file, 'EQUIL')
            if(equil_pos > 0):
                #delete equil and replace with restart
                #assemble new string for restart section
                ecl_data_file[equil_pos] = 'RESTART\n'
                ecl_data_file[equil_pos + 1] =  '\'' + self.old_simulation_title + '\' \t'
                ecl_data_file[equil_pos + 1] += str(int(self.restart_id) + timestep )  + ' /\n'
            else:
                restart_pos = util.search_section(ecl_data_file, "RESTART")
                if restart_pos > 0:
                    #assemble new string for restart section
                    ecl_data_file[restart_pos + 1] =  '\'' + self.old_simulation_title + '\' \t'
                    ecl_data_file[restart_pos + 1] += str(int(self.restart_id) + timestep)  + ' /\n'
        if timestep > 1:
            restart_pos = util.search_section(ecl_data_file, "RESTART")
            if restart_pos > 0:
                #assemble new string for restart section
                ecl_data_file[restart_pos + 1] =  '\'' + self.old_simulation_title + '\' \t'
                ecl_data_file[restart_pos + 1] += str(int(self.restart_id) + timestep )  + ' /\n'
                # print('Assembled string for restart:')
                # print('\'' + self.old_simulation_title + '\'', str(int(self.restart_id) + timestep )  + ' /\n')
                # print( 'Restart id: ', self.restart_id, ' timestep: ', timestep)

            # OPM-specific restart header workaround (.X0000 copy)
            # only needed for OPM Flow. ECLIPSE typically produces the header itself.
            if str(self.simulator).upper() == "OPM" and timestep > 1:
                rst_file = os.path.join(
                    self.working_dir_loc,
                    f"{self.simulation_title_orig}_TSTEP_{timestep - 2}.X0000"
                )
                new_init_rst = os.path.join(
                    self.working_dir_loc,
                    f"{self.simulation_title_orig}_TSTEP_{timestep - 1}.X0000"
                )
                with open(rst_file, "rb") as fsrc, open(new_init_rst, "wb") as fdst:
                    fdst.write(fsrc.read())

        #now rearrange the well schedule section
        schedule_pos = util.search_section(ecl_data_file, "WCONINJE")
        if schedule_pos == -1:
            schedule_pos = util.search_section(ecl_data_file, "WCONPROD")

        #print(schedule_pos)

        if schedule_pos > 0:
            # delete the old well schedule
            del ecl_data_file[schedule_pos:]
            # append new well schedule
            # first calculate rate applied for each well
            well_count = len(self.well_names)
            well_target = abs(flowrate / well_count) / self.reservoir_compartments
            well_target_days = well_target * 60.0 * 60.0 *24.0

            #now construct new well schedule section
            #ecl_data_file.append('\n')

            if op_mode == 'charging':
                ecl_data_file.append("WCONINJE\n")
                for idx in range(len(self.well_names)):
                    line = '\'' + self.well_names[idx] + '\''
                    line += '\t\'GAS\'\t\'OPEN\'\t\'RATE\'\t'
                    line += str(well_target_days) + '\t'
                    line += '1*\t' + str(self.well_upper_BHP[idx]) + '/\n'
                    ecl_data_file.append(line)

            elif op_mode == 'discharging':
                ecl_data_file.append("WCONPROD\n")
                for idx in range(len(self.well_names)):
                    line = '\'' + self.well_names[idx] + '\''
                    line += '\t\'OPEN\'\t\'GRAT\'\t1*\t1*\t'
                    line += str(well_target_days) + '\t'
                    line += '1*\t1*\t' + str(self.well_lower_BHP[idx]) + '/\n'
                    ecl_data_file.append(line)

            elif op_mode == 'shut-in' or op_mode == 'init':
                ecl_data_file.append("WCONINJE\n")
                for idx in range(len(self.well_names)):
                    line = '\'' + self.well_names[idx] + '\''
                    line += '\t\'GAS\'\t\'OPEN\'\t\'RATE\'\t'
                    line += '0.0' + '\t'
                    line += '1*\t' + str(self.well_upper_BHP[idx]) + '/\n'
                    ecl_data_file.append(line)
            else:
                print('ERROR: operational mode not understood in timestep: ', timestep, ' is: ', op_mode)

            ecl_data_file.append('/')
            #finish schedule
            timestepsize_days = timestepsize / 60.0 / 60.0 / 24.0
            file_finish = ['\n', '\n', 'TSTEP\n', '1*' + str(timestepsize_days) + '\n', '/\n', '\n', '\n', 'END\n' ]
            ecl_data_file += file_finish


            #save to new file
            #if not op_mode == 'init':
            #    temp_path = self.working_dir_loc + self.current_simulation_title + '.DATA'
            #else:
            #    #print('ini mode')
            #    temp_path = self.working_dir_loc + self.simulation_title + '_init.DATA'
            # temp_path = self.working_dir_loc + self.current_simulation_title + '.DATA'
            temp_path = os.path.join(self.working_dir_loc, f"{self.current_simulation_title}.DATA")
            util.write_file(temp_path, ecl_data_file)

    def delete_sim_files(self, tstep):

        file_ending_unform = ".X"
        file_ending_form = ".F"
        temp_nr_str = ""
        restart_tstep = tstep - 1
        if restart_tstep < 0:
            # nothing to delete yet; the lag means we skip on the first call
            restart_suffixes = ()
        else:
            if restart_tstep == 0:
                temp_nr_str = "0001"
            else:
                if (restart_tstep + 1) <= 10:
                    temp_nr_str = "000" + str(restart_tstep)
                elif (restart_tstep + 1) <= 100:
                    temp_nr_str = "00" + str(restart_tstep)
                elif (restart_tstep + 1) <= 1000:
                    temp_nr_str = "0" + str(restart_tstep)
                else:
                    temp_nr_str = str(restart_tstep)

            file_ending_unform += temp_nr_str
            file_ending_form += temp_nr_str
            restart_suffixes = (file_ending_unform, file_ending_form)

        termination_list = [
            ".DBG", ".dbprtx", ".ECLEND", ".ECLRUN", ".GRID", ".EGRID", ".FGRID",
            ".h5", ".INIT", ".FINIT", ".INSPEC", ".FINSPEC", ".LOG", ".MSG",
            ".RSSPEC", ".FRSSPEC", ".SMSPEC", ".FSMSPEC", ".UNSMRY", ".FUNSMRY",
            ".PRTX", ".RTEMSG", ".RTELOG", ".CFE", ".default", ".session", ".sessionlock"
        ]

        for filename in os.listdir(self.working_dir_loc):
            if any(filename.endswith(ext) for ext in termination_list):
                util.delete_file(os.path.join(self.working_dir_loc, filename))

        # delete restart files (.X####, .F####) lagged by one timestep
        if restart_suffixes:
            for filename in os.listdir(self.working_dir_loc):
                if filename.endswith(restart_suffixes):
                    util.delete_file(os.path.join(self.working_dir_loc, filename))

    def execute_ecl(self, tstep, iter_step, op_mode):
        '''
        Function to call eclipse executable

        :param tstep: current timestep
        :param type: int
        :param op_mode: operational mode of storage simulation
        :param type: str
        :returns: no return value
        '''
        #import subprocess
        #import os

        if os.name == 'nt':
            simulation_path = os.path.join(self.working_dir_loc, f"{self.current_simulation_title}.DATA")

            if self.keep_ecl_logs == True:
                log_file_path = os.path.join(self.working_dir_loc,
                                                 f"log_{self.current_simulation_title}_{tstep}_{iter_step}.txt")

            else:
                log_file_path = 'NUL'
            temp = 'eclrun ' + self.simulator + ' ' + simulation_path + ' >' + log_file_path
            os.system(temp)

    def get_ecl_results(self, timestep, current_op_mode):
        '''
        Function to get the eclipse results from the *.RSM file and analyze the results

        :param timestep: current timestep
        :param type: int
        :param current_op_mode: operational mode, either 'charging', 'discharging' or 'shut-in'
        :param type: str
        :returns: returns a tuple of float values containing pressure and actual storage flow rate
        '''

        filename = os.path.join(self.working_dir_loc, self.current_simulation_title + '.RSM')
        results = util.get_file(filename)

        #sort the rsm data to a more uniform dataset
        if self.simulator == 'e300' or self.simulator == 'ECLIPSE':
            reorderd_rsm_data = self.rearrange_rsm_data_array(results)
            well_results = util.contract_data_array(reorderd_rsm_data)
            entry_count_temp = 4 if self.simulator == 'e300' else 5

        elif self.simulator == 'OPM':
            raw_opm_data = self.rearrange_rsm_data_array_opm(results)
            # bypass contract_data_array, manually split the 4 clean tab-separated rows
            well_results = [row.rstrip('\n').split('\t') for row in raw_opm_data]
            entry_count_temp = 4  # building 4 rows (Headers, Units, Wells, Data)

        else:
            print(f"ERROR: Simulator '{self.simulator}' not recognised.")
            return [0.0, 0.0]

        # check for truncated or overly long data lines in the summary file
        values = len(well_results) - entry_count_temp
        if values > 1:
            print('Warning: possible loss of data, too many data lines in RSM file')

        #data structures to save the flowrates, pressures and names of all individual wells
        well_pressures = []
        well_flowrates_days = []
        well_flowrates = []
        well_names = []
        well_names_loc = []
        flowrate_actual = 0.0

        # get well pressures
        pressure_keyword = 'WBHP'
        bhp_positions = util.get_string_positions(well_results[0], pressure_keyword)

        for i in bhp_positions:
            well_pressures.append(float(well_results[-1][i]))
            well_names.append(well_results[2][i])

            # catch zero pressures and default to BHP limits (e.g. well shut-in or dropped out)
            if well_pressures[-1] == 0.0:
                print('Problem: well pressure for well ', well_names[-1], ' is zero. Setting to corresponding BHP limit' )
                bhp_limits_well = self.get_well_bhp_limits(well_names[-1])
                if current_op_mode == 'discharging':
                    well_pressures[-1] = bhp_limits_well[0]
                elif current_op_mode == 'charging' or current_op_mode == 'shut-in':
                    well_pressures[-1] = bhp_limits_well[1]
                else:
                    print('Problem: could not determine operational mode, assuming injection')
                    well_pressures[-1] = bhp_limits_well[1]

        # now get well flow rates
        if current_op_mode == 'discharging':  # negative flow rates
            flow_keyword = 'WGPR'
            flow_positions = util.get_string_positions(well_results[0], flow_keyword)
            for i in flow_positions:
                well_flowrates_days.append(float(well_results[-1][i]))
                well_names_loc.append(well_results[2][i])

        elif current_op_mode == 'charging':  # positive flow rates
            flow_keyword = 'WGIR'
            flow_positions = util.get_string_positions(well_results[0], flow_keyword)
            for i in flow_positions:
                well_flowrates_days.append(float(well_results[-1][i]))
                well_names_loc.append(well_results[2][i])

        elif current_op_mode == 'shut-in' or current_op_mode == 'init':
            #do nothing
            pass
        else:
            print('Warning: operational mode not understood, assuming shut-in at timestep: ', timestep)

        if ( current_op_mode == 'charging' or current_op_mode == 'discharging'):
            # go through well names list and compare strings.
            # rearrange if necessary to get correct match for pressures and flowrates
            correct_idx = []
            for i in range(len(well_names)):
                if well_names[i] == well_names_loc[i]:
                    correct_idx.append(i)
                else:
                    target_str = well_names[i]
                    for j in range(len(well_names_loc)):
                        if well_names_loc[j] == target_str:
                            correct_idx.append(j)
            #sort entries in well_flowrates based on correct_idx
            well_flowrates_temp = well_flowrates_days.copy()
            for i, idx in enumerate(correct_idx):
                well_flowrates_days[i] = well_flowrates_temp[idx]

            #change unit of flowrates to sm3/s from sm3/d
            for i in range(len(well_flowrates_days)):
                well_flowrates.append(well_flowrates_days[i] / 60.0 / 60.0 / 24.0)

            flowrate_actual = sum(well_flowrates)

            if flowrate_actual > 0.0:
                #calculate average pressure
                pressure_actual = 0.0
                for i in range(len(well_pressures)):
                    pressure_actual += well_pressures[i] * well_flowrates[i]
                pressure_actual = pressure_actual / flowrate_actual
            else:
                #fallback to simple average if no flow
                pressure_actual = sum(well_pressures) / float(len(well_pressures))
        else:
            # shut-in state: simple average of well pressures
            if len(well_pressures) > 0:
                pressure_actual = sum(well_pressures) / float(len(well_pressures))
            else:
                pressure_actual = 0.0

        return [pressure_actual, flowrate_actual]

    def get_well_bhp_limits(self, well_name):
        '''
        function to obtain pressure limits for a given well
        :param well_name: well identifier used to search well list
        :param type: string
        :returns: tuple of float, lower and upper BHP limit
        '''
        for i in range(len(self.well_names)):
            if self.well_names[i] == well_name:
                return [self.well_lower_BHP[i], self.well_upper_BHP[i]]

        return [0.0, 0.0]

    def run_proxy(self, target_flowrate, tstep, iter_step, tstepsize, current_mode):
        """
        function acting as a wrapper for using PROXY simulator as a storage simulator

        :param target_flow_rate: target storage flow rate in sm3/d
        :param tstep: current timestep
        :param iter_step: current iteration step
        :param tstepsize: length of current timestep
        :param current_mode: current operational mode, either 'charging', 'discharging' or 'shut-in'
        :returns: tuple of new pressure at the well (in reservoir) and actual (achieved) storage flow rate
        """

        if tstep < 0 or current_mode == 'init':
            self.current_simulation_title = self.simulation_title_orig

        if tstep >= 0:
            self.old_simulation_title = self.current_simulation_title
            self.current_simulation_title = f"{self.simulation_title_orig}_TSTEP_{tstep}_{iter_step}"

        if not current_mode == 'init':
            print('Running storage simulation')
            print(f"{'Simulation title:':30s} {self.current_simulation_title}")
            print(f"{'Timestep / iteration:':30s} {int(tstep)} / {int(iter_step)}")
            print(f"{'Timestep size [s]:':30s} {tstepsize:.0f}")
            print(f"{'Target flowrate [kg/s]:':30s} {target_flowrate:.6f}")  # storage flow rate
            print(f"{'Target flowrate [sm3/s]:':30s} {(target_flowrate / self.surface_density):.6f}")
            print(f"{'Operational mode:':30s} {current_mode}")
        else:
            print('Running storage simulation to obtain initial pressure')

        # change unit of flowrates to kg/s from kg/d
        target_flowrate = target_flowrate / self.surface_density * 60.0 * 60.0 * 24.0

        self.rework_proxy_data(tstep, iter_step, target_flowrate, current_mode)

        self.execute_proxy()

        proxy_results = self.get_proxy_results(current_mode)

        self.rework_proxy_results(tstep, iter_step)

        if not current_mode == 'init':
            print("-" * 50)
            print(f"{'Pressure actual [bar]:':30s} {'%.6f' % proxy_results[0]}")
            print(f"{'Flowrate actual [kg/s]:':30s} {'%.6f' % proxy_results[1]}")
            print(f"{' ':30s} {'%.6f' % (proxy_results[1] / self.surface_density)}" ' [sm3/s]')
        else:
            print(f"{'Initial pressure is:':30s} {'%.6f' % proxy_results[0]}" '[bar]')
        print("-" * 50)

        return (proxy_results[1], proxy_results[0])

    def execute_proxy(self):
        '''
        function to call PROXY simulator executable

        :returns: no return value
        '''

        if os.name == 'nt':
            # simulation_path = ''
            simulation_path = os.path.join(self.working_dir_loc,
                                           self.simulation_title_orig)  # proxy simulator uses only one unique name

            if self.keep_ecl_logs == True:
                if self.keep_ecl_logs == True:
                    log_file_path = os.path.join(self.working_dir_loc, f"{self.current_simulation_title}.log")

            else:
                log_file_path = 'NUL'
            temp = f'{self.simulator_path}\\sAGSS.exe {simulation_path} > {log_file_path}'

            os.system(temp)

    def rework_proxy_data(self, timestep, iter_step, flowrate, op_mode):
        '''
        function to change settings in the PROXY input file required for the storage simulation

        :param timestep: current timestep of simulation, type: int
        :param flowrate: current target storage flow rate from power plant simulation, type: float
        :param op_mode: current operational mode, either 'charging', 'discharging' or 'shut-in', type: str
        :returns: no return value
        '''
        # open and read eclipse data file

        schedule_path = os.path.join(self.working_dir_loc, f"{self.simulation_title_orig}.schedule")
        schedule_file = util.get_file(schedule_path)
        flowrate_pos = util.search_section(schedule_file, ' $CURVE') + 1

        if timestep == 0:
            pass

        # update reservoir pressure
        if  timestep >= 1 and iter_step == 0: #maybe iter_step == 0 is enough

            resprop_path = os.path.join(self.working_dir_loc, f"{self.simulation_title_orig}.res_prop")
            resprop_file = util.get_file(resprop_path)
            pressure_pos = util.search_section(resprop_file, ' $INITIAL_PRESSURE') + 1

            # retrieve the previous flow rate and mass volume using the results from the current simulation
            result_temp_path = os.path.join(self.working_dir_loc, f"{self.old_simulation_title}.RESULT_WELLS")

            results = util.get_file(result_temp_path)

            if len(results) <= 1:
                print('Warning: there is no simulation result')
                return [None, None]

            # extract header information
            header = results[0].strip().split('\t')

            # find indices of relevant keyword
            pressure_idx = util.get_string_positions(header, 'RES_PRESS')

            # get data from second line (first line shows variable unit)
            data = [line.strip().split('\t') for line in results[2:]]
            pressure_res = [float(data[0][i]) for i in pressure_idx]

            # update pressure reservoir pressure in INITIAL PRESSURE keyword
            resprop_file[pressure_pos] = f' {round(pressure_res[0], 3)}\n'

            util.write_file(resprop_path, resprop_file)

        if op_mode == 'charging':
           schedule_file[flowrate_pos] = f' 0 {round(flowrate, 3)}\n'

        elif op_mode == 'discharging':
           schedule_file[flowrate_pos] = f' 0 {round(-flowrate, 3)}\n'

        elif op_mode == 'shut-in' or op_mode == 'init':
           schedule_file[flowrate_pos] = ' 0 0\n'

        # update flow rate in the CURVE keyword
        util.write_file(schedule_path, schedule_file)

    def get_proxy_results(self, current_op_mode):
        '''
        function to get the PROXY results from the *.RESULTS_WELLS file and derive the pressure and actual flow rate data

        :param timestep: current timestep, type: int
        :param current_op_mode: operational mode, either 'charging', 'discharging' or 'shut-in', type: str
        :returns: returns a tuple of float values containing pressure and actual storage flow rate
        '''
        file_path = os.path.join(self.working_dir_loc, f"{self.simulation_title_orig}.RESULT_WELLS")
        results = util.get_file(file_path)

        if len(results) <= 1:
            print('Warning: there is no simulation result')
            return [None, None]

        # extract header information
        header = results[0].strip().split('\t')

        # find indices of relevant columns
        bhp_idx = util.get_string_positions(header, 'BHP')
        mfr_idx = util.get_string_positions(header, 'MFR')

        # extract rate and pressure data from second line (first is unit row)
        data = [line.strip().split('\t') for line in results[2:]]

        bhp_data = [float(data[0][i]) for i in bhp_idx]
        mfr_data = [float(data[0][i]) for i in mfr_idx]

        # storage pressure based on each WBHP
        pressure_actual = sum(bhp_data) / len(bhp_data)
        flowrate_actual = sum(mfr_data) / 60.0 / 60.0 / 24.0

        if current_op_mode == 'discharging':
            flowrate_actual = -flowrate_actual
        elif current_op_mode == 'init':
            flowrate_actual = flowrate_actual / 60.0 / 60.0 / 24.0

        return [pressure_actual, flowrate_actual]

    def rework_proxy_results(self, timestep, iter_step):
        """
        function to rework the PROXY results file name to include the current time step and iteration step and rename the current results file

        :param timestep: the current time step, type: int
        :param iter_step: the current iteration step, type: int
        """
        # define the new file name
        if timestep < 0:
            new_filename = os.path.join(self.working_dir_loc,
                                        f"{self.simulation_title_orig}_TSTEP_{timestep}_{iter_step}.RESULT_WELLS")
        else:
            new_filename = os.path.join(self.working_dir_loc, f"{self.current_simulation_title}.RESULT_WELLS")

        # rename the current results file
        old_filename = os.path.join(self.working_dir_loc, f"{self.simulation_title_orig}.RESULT_WELLS")
        os.rename(old_filename, new_filename)

    def execute_opm(self, tstep, iter_step):

        simulation_path = os.path.join(self.working_dir_loc, self.current_simulation_title + ".DATA")

        if self.keep_ecl_logs == True:
            log_file_path = os.path.join(self.working_dir_loc, f"log_{self.current_simulation_title}_{tstep}_{iter_step}.txt")
        else:
            log_file_path = None

        if os.name == 'nt':
            # convert Windows path to WSL path
            simulation_path_wsl = simulation_path.replace("\\", "/")
            drive = simulation_path_wsl[0].lower()
            simulation_path_wsl = f"/mnt/{drive}/{simulation_path_wsl[3:]}"

            run_cmd = f"{self.simulator_path} {simulation_path_wsl} --enable-opm-rst-file=true --parsing-strictness=low"

            if log_file_path is not None:
                log_file_path_wsl = log_file_path.replace("\\", "/")
                drive = log_file_path_wsl[0].lower()
                log_file_path_wsl = f"/mnt/{drive}/{log_file_path_wsl[3:]}"
                run_cmd = run_cmd + f" > {log_file_path_wsl} 2>&1"
            else:
                # silence output when logs disabled
                run_cmd = run_cmd + " > /dev/null 2>&1"
            subprocess.run(["wsl", "bash", "-c", run_cmd])
            return

         # linux execution
        if os.name == "posix":
            run_cmd = [self.simulator_path, simulation_path, "--enable-opm-rst-file=True"]

            if log_file_path is not None:
                with open(log_file_path, "w", encoding="utf-8") as logf:
                    subprocess.run(run_cmd, stdout=logf, stderr=logf)
            else:
                subprocess.run(run_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
