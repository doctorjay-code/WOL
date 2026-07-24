import re
import socket
import logging
import requests

logger = logging.getLogger(__name__)

def format_mac_variants(mac_address: str) -> list[str]:
    """MAC 주소 형식을 다양한 포맷(colon, dash, raw) 리스트로 반환"""
    clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac_address).upper()
    if len(clean_mac) != 12:
        raise ValueError(f"유효하지 않은 MAC 주소입니다: {mac_address}")
    colon_mac = ':'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])
    dash_mac = '-'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])
    return [colon_mac, dash_mac, clean_mac]

def send_iptime_wol(iptime_url: str, username: str, password: str, target_mac: str) -> tuple[bool, str]:
    """
    ipTime 공유기 웹 관리자 페이지에 로그인하여 정확한 WOL(Wake-on-LAN) 전송을 실행합니다.
    - tmenu=iframe&smenu=expertconfwollist
    - act=wake
    - wakeupchk=MAC_ADDRESS
    """
    if not iptime_url or not username or not password or not target_mac:
        return False, "ipTime 공유기 접속 설정(URL, 계정, MAC 주소)이 부족합니다."

    url = iptime_url.strip().rstrip('/')
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'http://' + url

    try:
        mac_variants = format_mac_variants(target_mac)
        primary_mac = mac_variants[0]  # colon_mac (예: 0C:9D:92:62:81:1D)
    except ValueError as ve:
        return False, str(ve)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    })

    try:
        # [1/4] 메인 페이지 접속
        logger.info(f"[WOL 1/4] ipTime 메인 페이지 접속 중... ({url}/)")
        r0 = session.get(f"{url}/", timeout=10, allow_redirects=True)

        # [2/4] 로그인 핸들러 POST
        login_endpoint = f"{url}/sess-bin/login_handler.cgi"
        login_data = {
            'init_status': '1',
            'captcha_on': '0',
            'captcha_file': '',
            'username': username,
            'passwd': password
        }
        session.headers.update({
            'Referer': f"{url}/sess-bin/login_session.cgi",
            'Origin': url
        })

        logger.info(f"[WOL 2/4] 로그인 POST 시도 중...")
        login_resp = session.post(login_endpoint, data=login_data, timeout=10, allow_redirects=False)

        match = re.search(r"setCookie\('([^']+)'\)", login_resp.text)
        if match:
            session_id = match.group(1)
            session.cookies.set('efm_session_id', session_id)
            logger.info(f"[WOL 2/4] 세션 ID 획득: {session_id}")

            # [3/4] JS document.form.submit() (login.cgi GET)
            session.headers.update({'Referer': login_endpoint})
            session.get(f"{url}/sess-bin/login.cgi", timeout=10, allow_redirects=True)
            logger.info("[WOL 3/4] 세션 활성화 완료")
        else:
            # 구형 펌웨어 호환 로그인
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

        # [4/4] 진짜 ipTime WOL 전송 (expertconfwollist iframe 엔드포인트)
        wol_endpoint = f"{url}/sess-bin/timepro.cgi"
        session.headers.update({
            'Referer': f"{url}/sess-bin/timepro.cgi?tmenu=iframe&smenu=expertconfwollist"
        })

        logger.info(f"[WOL 4/4] ipTime 진짜 WOL 부팅 패킷 발송 (MAC: {primary_mac})")
        
        # 콜론, 대시 등 포맷별 타격
        for mac_fmt in mac_variants:
            real_payload = {
                'tmenu': 'iframe',
                'smenu': 'expertconfwollist',
                'act': 'wake',
                'wakeupchk': mac_fmt
            }
            wr = session.post(wol_endpoint, data=real_payload, timeout=5)
            logger.info(f"[WOL 4/4] POST (mac={mac_fmt}): status={wr.status_code}")

        logger.info(f"[WOL 4/4] 진짜 WOL 부팅 명령 전송 성공")
        return True, f"ipTime 공유기를 통해 컴퓨터(MAC: `{primary_mac}`)에 WOL 켜기 명령을 보냈습니다!"

    except requests.exceptions.Timeout as e:
        logger.error(f"[WOL] 타임아웃: {e}")
        return False, "ipTime 공유기 접속 시간이 초과되었습니다. (DDNS 주소 및 원격 접속 포트를 확인하세요)"
    except requests.exceptions.RequestException as e:
        logger.error(f"[WOL] 통신 에러: {e}")
        return False, f"ipTime 공유기 통신 에러: {str(e)}"
    except Exception as e:
        logger.error(f"[WOL] 예외 발생: {e}", exc_info=True)
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
