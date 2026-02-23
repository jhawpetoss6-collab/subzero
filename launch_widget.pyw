"""
Launch TM Widget silently (no console window).
Use this as a desktop shortcut or pin to taskbar.
Right-click -> "Pin to taskbar" or "Send to Desktop (create shortcut)"
"""
import os
import sys
import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
widget_path = os.path.join(script_dir, "terminal_widget.py")
terminal_path = os.path.join(script_dir, "custom_terminal.py")

# Launch the TM Widget
subprocess.Popen([sys.executable, widget_path])

# Optionally also launch the Custom Terminal alongside it:
# subprocess.Popen([sys.executable, terminal_path])
