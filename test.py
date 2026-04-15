from coupled_simulation.coupling import CouplingData
from coupled_simulation.powerplant import PowerPlantCoupling

cd = CouplingData("testdata/testcase_ECM2021_DREC_peak_pv/testcase_ecm2021.main_ctrl.json")
coupling = PowerPlantCoupling(cd, 1000, 3, 120, 50)
print(coupling.get_mass_flow(135, 100, "charge"))
print(coupling.get_mass_flow(60, 100, "discharge"))
print(coupling.get_mass_flow(80, 100, "discharge"))
print(coupling.get_mass_flow(80, 50, "discharge"))
print(coupling.get_mass_flow(110, 120, "discharge"))

cd = CouplingData("testdata/testcase_ECM2021_ACAES2_peak_pv/testcase_ecm2021.main_ctrl.json")
coupling = PowerPlantCoupling(cd, 1000, 3, 120, 50)
print(coupling.get_mass_flow(135, 100, "charge"))
print(coupling.get_mass_flow(60, 100, "discharge"))

cd = CouplingData("testdata/testcase_ECM2021_ACAES3_peak_pv/testcase_ecm2021.main_ctrl.json")
coupling = PowerPlantCoupling(cd, 1000, 3, 120, 50)
print(coupling.get_mass_flow(135, 100, "charge"))
print(coupling.get_mass_flow(90, 100, "discharge"))
