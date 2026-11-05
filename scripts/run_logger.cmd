@echo off
rem One pass of the forecast logger at low priority (called by Task Scheduler twice a day). Safe to run any time:
rem a half-day slot that is already stored is skipped.
cd /d C:\Users\Senai\Tempest-ARKNET
set OMP_NUM_THREADS=4
start "" /b /wait /belownormal .venv\Scripts\python.exe -u -m tempest.ops.logger
