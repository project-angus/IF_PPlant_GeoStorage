@echo off
:: rem simulators folder
set IF_PPlant_GeoStorage=....\IF_PPlant_GeoStorage\run_if.py
set "pythonpath=....Python\Python38" 
set "pythonexe=%pythonpath%\python.exe"

:: rem simulation input folder
set dir_path=....\SYNTH_RADIAL_CAES_IF

set main_ctrl_file="%dir_path%\scenario.main_ctrl.json"
set geostorage_dir="%dir_path%\geostorage"
set include_dir="%geostorage_dir%\include"

set geostorage_ctrl_file="%include_dir%\scenario.geostorage_ctrl.json"
set DATA_file="%include_dir%\GEOSTORAGE.DATA"

:: rem DELETE files in geostorage folder
del "%geostorage_dir%" *.X /Q
copy "%geostorage_ctrl_file%" "%geostorage_dir%"
copy "%DATA_file%" "%geostorage_dir%"
@echo off
rem Run Interface
"%pythonexe%" "%IF_PPlant_GeoStorage%" -i r"%main_ctrl_file%"
pause