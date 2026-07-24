Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\hyo02\Downloads\GitHub\WOL"
WshShell.Run "pythonw pc_agent.py", 0, False
