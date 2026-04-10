from tespy.tools.helpers import merge_dicts
from tespy.connections import Ref
from tespy.networks import Network
import os
import numpy as np


class ModelTemplate():

    def __init__(self, config) -> None:
        self.config = config
        os.makedirs(self.config["path"], exist_ok=True)

        self._design_path = os.path.join(self.config["path"], "design.json")
        self._stable_solution = os.path.join(self.config["path"], "_stable_solution.json")

        self.parameter_lookup = config["parameter_lookup"]
        self._create_network()

    def _create_network(self) -> None:
        self.nw = Network()
        self.nw.units.set_defaults(**self.config["units"])

    def _map_parameter(self, parameter: str) -> tuple:
        return self.parameter_lookup[parameter]

    def _map_to_input_dict(self, **kwargs) -> dict:
        input_dict = {}
        for param, value in kwargs.items():
            if param not in self.parameter_lookup:
                msg = (
                    f"The parameter {param} is not mapped to any input of the "
                    "model. The following parameters are available:\n"
                    f"{', '.join(self.parameter_lookup)}."
                )
                raise KeyError(msg)
            key = self._map_parameter(param)
            if key[-1] is None:
                input_dict = merge_dicts(
                    input_dict,
                    {key[0]: {key[1]: value}}
                )
            else:
                input_dict = merge_dicts(
                    input_dict,
                    {key[0]: {key[1]: {key[2]: value}}}
                )
        return input_dict

    def get_parameter(self, parameter: str) -> float:
        mapped = self._map_parameter(parameter)
        if mapped[0] == "Connections":
            return self.nw.get_conn(mapped[1]).get_attr(mapped[2]).val

        elif mapped[0] == "Components":
            return self.nw.get_comp(mapped[1]).get_attr(mapped[2]).val

        elif mapped[0] == "Customs":
            return self._get_customs(parameter)

    def set_parameters(self, **kwargs) -> None:
        input_dict = self._map_to_input_dict(**kwargs)
        if "Connections" in input_dict:
            for c, params in input_dict["Connections"].items():
                self.nw.get_conn(c).set_attr(**params)

        if "Components" in input_dict:
            for c, params in input_dict["Components"].items():
                self.nw.get_comp(c).set_attr(**params)

        if "Customs" in input_dict:
            self._set_customs(input_dict["Customs"])

    def _set_customs(self, specifications):
        pass

    def _get_customs(self, parameter):
        return None

    def save_design_state(self):
        self.nw.save(self._design_path)

    def export(self):
        self.nw.export(os.path.join(self.config["path"], "export.json"))

    def solve_model_design(self, **kwargs) -> None:
        self.set_parameters(**kwargs)

        self._solved = False
        self.nw.solve("design")

        if self.nw.status == 0:
            self._solved = True
        # is not required in this example, but could lead to handling some
        # stuff
        elif self.nw.status == 1:
            self._solved = False
        elif self.nw.status in [2, 3, 99]:
            # in this case model is very likely corrupted!!
            # fix it by running a presolve using the stable solution
            self._solved = False
            self.nw.solve("design", init_only=True, init_path=self._stable_solution)

    def solve_model_offdesign(self, **kwargs) -> None:
        self.set_parameters(**kwargs)

        self._solved = False
        self.nw.solve("offdesign", design_path=self._design_path)

        if self.nw.status == 0:
            self._solved = True
        elif self.nw.status in [1, 2, 3, 99]:
            # in this case model is very likely corrupted!!
            # fix it by running a presolve using the stable solution
            self._solved = False
            self.nw.solve("design", init_only=True, design_path=self._design_path, init_path=self._stable_solution)


class PowerPlant(ModelTemplate):

    @classmethod
    def from_json(cls, network_json, config):
        instance = cls(config)
        instance.nw = Network.from_json(network_json)
        return instance

    def _get_customs(self, parameter):
        if parameter == "well_number":
            c1 = self.nw.get_conn(self.config["well_mass_flow_connection"])
            return 1 / c1.m_ref.ref.factor

    def _set_customs(self, specifications):
        if "well_number" in specifications:
            well_num = specifications["well_number"]
            c1 = self.nw.get_conn(self.config["well_mass_flow_connection"])
            c2 = self.nw.get_conn(self.config["powerplant_mass_flow_connection"])
            c1.set_attr(m=Ref(c2, 1 / well_num, 0))

    def solve_model_offdesign_with_stepping(self, **kwargs) -> None:

        current_values = {}
        for key, value in kwargs.items():
            if value is None:
                self.set_parameters(**{key: value})
            else:
                current_values[key] = self.get_parameter(key)
                self.set_parameters(**{key: current_values[key]})

        steps = {}
        for key, value in current_values.items():
            if key == "well_pressure":
                num = int(abs(kwargs[key] - value) // 5) + 1
            elif key == "power":
                num = int(abs(kwargs[key] - value) // abs(0.1 * self.power_nominal)) + 1
            elif key == "powerplant_mass_flow":
                num = int(abs(kwargs[key] - value) // abs(0.05 * self.dot_m_nominal)) + 1
            else:
                num = 3

            # go from target value (kwargs[key]) to old value (value) in num steps
            # without the actual old value in the linspace, then reverse order
            steps[key] = np.linspace(kwargs[key], value, num, endpoint=False)[::-1]

        for key, stepping in steps.items():
            for step in stepping:
                self.solve_model_offdesign(**{key: step})
                if not self._solved:
                    return False

        return True

    def solve_model_design_with_stepping(self, **kwargs) -> None:

        current_values = {}
        for key, value in kwargs.items():
            if value is None:
                self.set_parameters(**{key: value})
            elif value == "var":
                self.set_parameters(**{key: value})
            else:
                current_values[key] = self.get_parameter(key)
                self.set_parameters(**{key: current_values[key]})

        steps = {}
        for key, value in current_values.items():
            if round(kwargs[key], 4) == round(value, 4):
                continue
            num = 3
            # go from target value (kwargs[key]) to old value (value) in num steps
            # without the actual old value in the linspace, then reverse order
            steps[key] = np.linspace(kwargs[key], value, num, endpoint=False)[::-1]

        for key, stepping in steps.items():
            for step in stepping:
                self.solve_model_design(**{key: step})
                if not self._solved:
                    return False

        return True
