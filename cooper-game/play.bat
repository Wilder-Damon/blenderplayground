@echo off
rem Launch Cooper's Park Run (expects Godot 4.7.2 in C:\dev\tools\Godot)
rem Note: "%~dp0." (with the dot) - a path ending in \" would escape the closing quote.
start "" "C:\dev\tools\Godot\Godot_v4.7.2-stable_win64.exe" --path "%~dp0."
