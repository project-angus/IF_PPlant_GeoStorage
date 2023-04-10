# Interface for Coupled Simulation of Geological Energy Storage and Power Plant Model

Zusammenfassung
+++++++++++++++

Die Schnittstelle zwischen Kraftwerk und geologischem Speicher stellt eine flexible Methode zum Koppeln einer Speichersimulation mit dem Betrieb von Kraftwerksanlagen. Der Speicherbetrieb wird mit Hilfe von Entscheidungsregeln gesteuert und übergibt die Schnittstellenparameter zwischen den Modellen automatisch. Der modulare Aufbau der Softwareschnittstelle erlaubt es, zwischen unterschiedlichen Simulationsmodellen für Speicher und Kraftwerk auszuwählen.

Abstract
++++++++

The Power Plant Geostorage Interface provides a flexible method to couple the simulation of a geological storage to the operation of a power plant. The interface provides a operation control logic and exchanges the interface parameters between the sotrage and the power plant model automatically. Due to a modular architecture, it is possible to choose between different simulation models for the power plant and the geological storage.

## Simulator coupling 

The simulator coupling strategy uses an operation splitting approach where the __[power plant](https://github.com/fgasa/IF_PPlant_GeoStorage/blob/master/coupled_simulation/powerplant.py)__ and __[geostorage](https://github.com/fgasa/IF_PPlant_GeoStorage/blob/master/coupled_simulation/geostorage.py)__ processes are separated but control over overall time-stepping and simulation execution is maintained. The input to the coupled simulator is an operational schedule, which determines whether the system should be __charging, discharging__, or __shut-in__.

__[Coupling](https://github.com/fgasa/IF_PPlant_GeoStorage/blob/master/coupled_simulation/coupling.py)__ of the power plant and geostorage models is achieved by exchanging mass flow rates and pressures at the well connections to the storage formation. The mass flow rates calculated via the power-plant model are converted using the surface density of air. The simulation moves to the next time step if the mass flows and storage pressures of the geostorage site and the power-plant model converge. In shut-in mode, the storage simulation is performed without mass injection or extraction. If the calculated mass flow rate exceeds the limit defined for the power-plant model, the mass flow is capped at the power-plant limit.

## License
This project is licensed under the [GPL-3.0 license](https://github.com/fgasa/IF_PPlant_GeoStorage/blob/master/LICENSE). You are free to use, modify and distribute the software under certain conditions. Any distribution of the software must also include a copy of the license and copyright notices.

If you use this work in your research, please cite the following publication: 

- Pfeiffer, W.T., Witte, F., Tuschy, I. and Bauer, S., 2021. Coupled power plant and geostorage simulations of porous media compressed air energy storage (PM-CAES). Energy Conversion and Management, 249, p.114849.