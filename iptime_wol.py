import re
import socket
import logging
import requests

logger = logging.getLogger(__name__)

def format_mac_for_iptime(mac_address: str) -> str:
    """MAC 주소 형식을 ipTime 공유기가 인식할 수 있는 AA-BB-CC-DD-EE-FF 형식으로 변환"""
    clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac_address)
    if len(clean_mac) != 12:
        raise ValueError(f"유효하지 않은 MAC 주소입니다: {mac_address}")
    return '-'.join([clean_mac[i:i+2].upper() for i in range(0, 12, 2)])

def send_iptime_wol(iptime_url: str, username: str, password: str, target_mac: str) -> tuple[bool, str]:
    """
    ipTime 공유기 웹 관리자 페이지에 로그인하여 원격 WOL(Wake-on-LAN)을 실행합니다.
    N102E 펌웨어 호환(tmenu, smenu) 및 구형 펌웨어 호환(tmenukey, smenukey)을 동시 지원합니다.
    Returns: (성공여부: bool, 메시지: str)
    """
    if not iptime_url or not username or not password or not target_mac:
        return False, "ipTime 공유기 접속 설정(URL, 계정, MAC 주소)이 부족합니다."

    url = iptime_url.strip().rstrip('/')
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url

    try:
        formatted_mac = format_mac_for_iptime(target_mac)
    except ValueError as ve:
        return False, str(ve)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f"{url}/sess-bin/login_session.cgi"
    })

    try:
        # 1. ipTime 로그인 핸들러 요청
        login_endpoint = f"{url}/sess-bin/login_handler.cgi"
        login_data = {
            'init_status': '1',
            'captcha_on': '0',
            'captcha_file': '',
            'username': username,
            'passwd': password
        }

        logger.info(f"ipTime 공유기({url}) 로그인 시도 중...")
        login_resp = session.post(login_endpoint, data=login_data, timeout=10)

        # 2. JavaScript의 setCookie('session_id') 추출
        match = re.search(r"setCookie\('([^']+)'\)", login_resp.text)
        if match:
            session_id = match.group(1)
            session.cookies.set('efm_session_id', session_id)
            logger.info(f"ipTime 세션 ID 획득 성공: {session_id}")
        else:
            # 구형 펌웨어 호환 로그인 (cgi-bin/timepro.cgi)
            legacy_endpoint = f"{url}/cgi-bin/timepro.cgi"
            legacy_data = {
                'tmenukey': 'http',
                'init_page': 'login',
                'username': username,
                'passwd': password
            }
            legacy_resp = session.post(legacy_endpoint, data=legacy_data, timeout=10)
            if "fail" in legacy_resp.text.lower() or "login" in legacy_resp.text.lower():
                return False, "ipTime 로그인 실패: 비밀번호 또는 아이디가 올바르지 않습니다."

        # 3. WOL 메뉴로 이동 및 MAC 등록/켜기 전송
        wol_endpoint = f"{url}/sess-bin/timepro.cgi"
        session.headers.update({
            'Referer': f"{url}/sess-bin/timepro.cgi?tmenu=expertconf&smenu=wol"
        })
        
        # 3-1. ipTime WOL 리스트에 자동 등록 (미등록 시 WOL 불가능한 현상 예방)
        add_data = {
            'tmenu': 'expertconf',
            'smenu': 'wol',
            'tmenukey': 'expertconf',
            'smenukey': 'wol',
            'act': 'add',
            'pcname': 'MYPC',
            'mac': formatted_mac
        }
        session.post(wol_endpoint, data=add_data, timeout=5)

        # 3-2. WOL 켜기 전송 (N102E 호환 tmenu/smenu + 구형 tmenukey/smenukey 파라미터 조합)
        wol_data = {
            'tmenu': 'expertconf',
            'smenu': 'wol',
            'tmenukey': 'expertconf',
            'smenukey': 'wol',
            'act': 'wakeup',
            'mac': formatted_mac,
            'chk': formatted_mac,
            'chk[]': formatted_mac
        }

        logger.info(f"ipTime WOL 요청 발송 중 (MAC: {formatted_mac})...")
        wol_resp = session.post(wol_endpoint, data=wol_data, timeout=10)

        if wol_resp.status_code == 200:
            return True, f"ipTime 공유기를 통해 컴퓨터(MAC: `{formatted_mac}`)에 WOL 켜기 명령을 보냈습니다!"
        else:
            return False, f"WOL 요청 실패 (응답 코드: {wol_resp.status_code})"

    except requests.exceptions.Timeout:
        return False, "ipTime 공유기 접속 시간이 초과되었습니다. (DDNS 주소 및 원격 접속 포트를 확인하세요)"
    except requests.exceptions.RequestException as e:
        return False, f"ipTime 공유기 통신 에러: {str(e)}"
    except Exception as e:
        return False, f"WOL 실행 중 오류 발생: {str(e)}"


def send_udp_wol(target_mac: str) -> tuple[bool, str]:
    """
    동일한 집 내부 네트워크(LAN) 환경일 때 직접 UDP 매직 패킷 브로드캐스트 발송 (보조용)
    """
    try:
        clean_mac = re.sub(r'[^a-fA-F0-9]', '', target_mac)
        if len(clean_mac) != 12:
            return False, "유효하지 않은 MAC 주소 형식입니다."
        
        mac_bytes = bytes.fromhex(clean_mac)
        magic_packet = b'\xff' * 6 + mac_bytes * 16

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(magic_packet, ('255.255.255.255', 9))
            s.sendto(magic_packet, ('255.255.255.255', 7))

        formatted_mac = '-'.join([clean_mac[i:i+2].upper() for i in range(0, 12, 2)])
        return True, f"로컬 LAN 브로드캐스트로 매직 패킷(MAC: `{formatted_mac}`)을 보냈습니다!"
    except Exception as e:
        return False, f"로컬 WOL 발송 실패: {str(e)}"
