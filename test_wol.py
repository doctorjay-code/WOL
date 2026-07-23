import requests
import re

s = requests.Session()
s.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'http://hyo02040.iptime.org:14817/sess-bin/login_session.cgi'
})

login_data = {
    'init_status': '1',
    'captcha_on': '0',
    'captcha_file': '',
    'username': 'hyo02040',
    'passwd': 'jFLUK8GDtEr8ixY'
}

r = s.post('http://hyo02040.iptime.org:14817/sess-bin/login_handler.cgi', data=login_data)
match = re.search(r"setCookie\('([^']+)'\)", r.text)

if match:
    session_id = match.group(1)
    s.cookies.set('efm_session_id', session_id)
    
    # 1. Add MAC to WOL table
    add_data = {
        'tmenu': 'expertconf',
        'smenu': 'wol',
        'tmenukey': 'expertconf',
        'smenukey': 'wol',
        'act': 'add',
        'pcname': 'MYPC',
        'mac': '70-5D-CC-99-BF-7A'
    }
    r_add = s.post('http://hyo02040.iptime.org:14817/sess-bin/timepro.cgi', data=add_data)
    print("Add status:", r_add.status_code)

    # 2. Wakeup WOL
    wol_data = {
        'tmenu': 'expertconf',
        'smenu': 'wol',
        'tmenukey': 'expertconf',
        'smenukey': 'wol',
        'act': 'wakeup',
        'mac': '70-5D-CC-99-BF-7A',
        'chk': '70-5D-CC-99-BF-7A'
    }
    r_wol = s.post('http://hyo02040.iptime.org:14817/sess-bin/timepro.cgi', data=wol_data)
    print("Wakeup status:", r_wol.status_code, len(r_wol.text))
