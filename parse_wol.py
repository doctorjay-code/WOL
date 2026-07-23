import re

with open("reframe.html", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Find all form names or document.xxx_fm
matches = re.findall(r'document\.([a-zA-Z0-9_]+_fm)', text)
print("Form names found:", set(matches))

# Find all functions containing _fm
funcs = re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\([^)]*\)', text)
wol_funcs = [fn for fn in funcs if 'wol' in fn.lower() or 'pc' in fn.lower()]
print("WOL functions found:", set(wol_funcs))
