import re

with open("wol_page.html", "r", encoding="utf-8", errors="ignore") as f:
    text = f.read()

# Find any URLs or script paths mentioned in javascript strings
matches = re.findall(r'["\']([^"\'\s]+\.cgi[^"\'\s]*)["\']', text)
print("CGI references in JS:", set(matches))
