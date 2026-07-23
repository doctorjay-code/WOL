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
    
    # Try fetching wol iframe directly
    urls = [
        'http://hyo02040.iptime.org:14817/sess-bin/timepro.cgi?tmenu=expertconf&smenu=wol&act=main',
        'http://hyo02040.iptime.org:14817/sess-bin/timepro.cgi?tmenu=expertconf&smenu=wol&act=body',
        'http://hyo02040.iptime.org:14817/sess-bin/timepro.cgi?tmenu=expertconf&smenu=wol&act=frame'
    ]
    for u in urls:
        res = s.get(u)
        print(u, res.status_code, len(res.text))
        for line in res.text.splitlines():
            if 'form' in line.lower() or 'mac' in line.lower() or 'wakeup' in line.lower():
                print("  ->", line[:150])
