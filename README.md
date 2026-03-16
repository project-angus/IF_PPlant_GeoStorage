# Interface for Coupled Simulation of Geological Energy Storage and Power Plant Model

## Zusammenfassung

Die Schnittstelle zwischen Kraftwerk und geologischem Speicher stellt eine flexible Methode zum Koppeln einer Speichersimulation mit dem Betrieb von Kraftwerksanlagen. Der Speicherbetrieb wird mit Hilfe von Entscheidungsregeln gesteuert und übergibt die Schnittstellenparameter zwischen den Modellen automatisch. Der modulare Aufbau der Softwareschnittstelle erlaubt es, zwischen unterschiedlichen Simulationsmodellen für Speicher und Kraftwerk auszuwählen.

## Abstract

The Power Plant Geostorage Interface provides a flexible method to couple the simulation of a geological storage to the operation of a power plant. The interface provides a operation control logic and exchanges the interface parameters between the sotrage and the power plant model automatically. Due to a modular architecture, it is possible to choose between different simulation models for the power plant and the geological storage.

## Simulator coupling 

The simulator coupling strategy uses an operation splitting approach where the __power plant__ and __geostorage__ processes are separated but control over overall time-stepping and simulation execution is maintained. The input to the coupled simulator is an operational schedule, which determines whether the system should be __charging, discharging__ or __shut-in__.

__Coupling__ of the power plant and geostorage models is achieved by exchanging mass flow rates and pressures at the well connections to the storage formation. The mass flow rates calculated via the power-plant model are converted using the surface density of stored fluid. The simulation moves to the next time step if the mass flows and storage pressures of the geostorage site and the power-plant model converge. In shut-in mode, the storage simulation is performed without mass injection or withdrawal. If the calculated mass flow rate exceeds the limit defined for the power-plant model, the mass flow is capped at the power-plant limit.

The framework is designed to support __different simulators__. Currently the following storage simulators are maintained within the interface:

- Commercial reservoir simulator (__black-oil and compositional models__)
- Open-source reservoir simulator: __OPM Flow__
- In-house __semi-analytical proxy simulator__

The modular architecture allows switching between these simulators without modifying the coupling logic, enabling both high-fidelity reservoir simulations and computationally efficient proxy-based workflows.

## License
This project is licensed under the [GPL-3.0 license](https://github.com/fgasa/IF_PPlant_GeoStorage/blob/master/LICENSE). You are free to use, modify and distribute the software under certain conditions. Any distribution of the software must also include a copy of the license and copyright notices.

If you use this work in your research, please cite the following publication: 

- Pfeiffer, W.T., Witte, F., Tuschy, I. and Bauer, S., 2021. Coupled power plant and geostorage simulations of porous media compressed air energy storage (PM-CAES). Energy Conversion and Management, 249, p.114849, doi.org/10.1016/J.ENCONMAN.2021.114849
- Gasanzade, F. and Bauer, S., 2025. Approximating coupled power plant and geostorage simulations for compressed air energy storage in porous media. Applied Energy, 380, 125070, doi.org/10.1016/j.apenergy.2024.125070