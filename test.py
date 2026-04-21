from coupled_simulation.coupling import CouplingData
from coupled_simulation.powerplant import PowerPlantCoupling

# cd = CouplingData("testcases/scerun_APEN2025_DREC_2030/scenario_APEN2025.main_ctrl.json")
# coupling = PowerPlantCoupling(cd, 1000, 3, 120, 50)
# print(coupling.get_mass_flow(135, 100, "charge"))
# print(coupling.get_mass_flow(60, 100, "discharge"))
# print(coupling.get_mass_flow(80, 100, "discharge"))
# print(coupling.get_mass_flow(80, 50, "discharge"))
# print(coupling.get_mass_flow(110, 120, "discharge"))

# cd = CouplingData("testcases/testcase_ECM2021_ACAES2_peak_pv/testcase_ecm2021.main_ctrl.json")
# coupling = PowerPlantCoupling(cd, 1000, 3, 120, 50)
# print(coupling.get_mass_flow(135, 100, "charge"))
# print(coupling.get_mass_flow(60, 100, "discharge"))

# cd = CouplingData("testcases/testcase_ECM2023_ACAES3_peak_pv/testcase_ecm2023.main_ctrl.json")
# coupling = PowerPlantCoupling(cd, 1000, 3, 120, 50)
# print(coupling.get_mass_flow(135, 100, "charge"))
# print(coupling.get_mass_flow(90, 100, "discharge"))


# cd = CouplingData("testcases/testcase_ANGUS_H2/testcase_h2_angus.main_ctrl.json")
# coupling = PowerPlantCoupling(cd, 1000, 3, 120, 50)
# print(coupling.get_mass_flow(135, 100, "charge"))
# print(coupling.get_mass_flow(50, 100, "discharge"))
# print(coupling.get_mass_flow(60, 50, "discharge"))
# print(coupling.get_mass_flow(40, 110, "discharge"))

cd = CouplingData("testcases/testcase_CCS_10MW/testcase_ccs.main_ctrl.json")
coupling = PowerPlantCoupling(cd, 1000, 3, 220, 100)
print(coupling.get_mass_flow(10, 190, "charge"))
print(coupling.get_mass_flow(8, 200, "charge"))
print(coupling.get_mass_flow(12, 170, "charge"))
print(coupling.get_mass_flow(7, 220, "charge"))
print(coupling.get_power(20, 200, "charge"))
