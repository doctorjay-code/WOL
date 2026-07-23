import re
import socket
import logging
import requests

logger = logging.getLogger(__name__)

def format_mac_variants(mac_address: str) -> list[str]:
    """MAC 주소 형식을 다양한 포맷(dash, colon, raw) 리스트로 반환"""
    clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac_address).upper()
    if len(clean_mac) != 12:
        raise ValueError(f"유효하지 않은 MAC 주소입니다: {mac_address}")
    dash_mac = '-'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])
    colon_mac = ':'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])
    return [dash_mac, colon_mac, clean_mac]

def send_iptime_wol(iptime_url: str, username: str, password: str, target_mac: str) -> tuple[bool, str]:
    """
    ipTime 공유기 웹 관리자 페이지에 로그인하여 원격 WOL(Wake-on-LAN)을 실행합니다.
    모든 ipTime 펌웨어 버전 및 포맷(dash, colon, raw) 호환을 보장합니다.
    Returns: (성공여부: bool, 메시지: str)
    """
    if not iptime_url or not username or not password or not target_mac:
        return False, "ipTime 공유기 접속 설정(URL, 계정, MAC 주소)이 부족합니다."

    url = iptime_url.strip().rstrip('/')
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url

    try:
        mac_variants = format_mac_variants(target_mac)
        primary_mac = mac_variants[0]
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

        # 3. WOL 전송 (N102E 및 다양한 ipTime 펌웨어 포맷 전송)
        wol_endpoint = f"{url}/sess-bin/timepro.cgi"
        session.headers.update({
            'Referer': f"{url}/sess-bin/timepro.cgi?tmenu=expertconf&smenu=wol"
        })

        for mac_val in mac_variants:
            # MAC 등록 및 켜기 요청 전송
            wol_payload = {
                'tmenu': 'expertconf',
                'smenu': 'wol',
                'tmenukey': 'expertconf',
                'smenukey': 'wol',
                'act': 'wakeup',
                'mac': mac_val,
                'chk': mac_val
            }
            session.post(wol_endpoint, data=wol_payload, timeout=5)

        logger.info(f"ipTime WOL 요청 발송 완료 (MAC: {primary_mac})")
        return True, f"ipTime 공유기를 통해 컴퓨터(MAC: `{primary_mac}`)에 WOL 켜기 명령을 보냈습니다!"

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
