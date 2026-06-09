"""

XSIAM XQL Public API 자동화

  ① start_xql_query           → execution_id

  ② get_query_results         → 결과 (1000건 미만이면 그대로 저장)

  ③ get_query_results_stream  → stream_id 로 대용량 결과 받아서 저장 (gunzip × 2)

출력: results.json

"""

from __future__ import print_function

import io
import json
import gzip
import sys
import time
import datetime

try:
    import requests
except ImportError:
    print("ERROR: pip install requests")
    sys.exit(1)

# 2.7 unicode / 3.x str 호환
try:
    text_type = unicode
except NameError:
    text_type = str

# ============================================================
# 환경 설정
# ============================================================
BASE_URL  = "https://api-skiens.xdr.sg.paloaltonetworks.com/public_api/v1"
AUTH_KEY  = "IUKj5ffcEksaZLhu613P0S9xwO8vyo3gCv2iMl33BNsKsmgnw8jbLMqINLXesMpC0Bsbig7obf1JVRSxPTMXUcGVTpjX4f85psuUSWcVfKwnCXdRs9p1BnbGlSNrwX0P"
AUTH_ID   = "6"

HEADERS = {
    "x-xdr-auth-id": AUTH_ID,
    "Authorization":  AUTH_KEY,
    "Content-Type":   "application/json",
}

OUTPUT_FILE       = "Install_log.json"
POLL_INTERVAL_SEC = 3
POLL_TIMEOUT_SEC  = 600
RESULT_LIMIT      = 1000

# ╔══════════════════════════════════════════════════════════╗
# ║                                                          ║
# ║   ### [쿼리 변경 자리] ###  ← 다른 쿼리 돌릴 땐 여기만!   ║
# ║                                                          ║
# ╠══════════════════════════════════════════════════════════╣

XQL_QUERY = """
dataset = xdr_data
| filter event_type = ENUM.REGISTRY
| filter action_registry_key_name contains "CurrentVersion\\Uninstall"
| filter action_registry_value_name in ("DisplayName", "InstallLocation")
| alter display_name = if(action_registry_value_name = "DisplayName", action_registry_data, null)
| alter install_location = if(action_registry_value_name = "InstallLocation", action_registry_data, null)
| comp values(display_name) as display_name_arr,
       values(install_location) as install_location_arr,
       values(agent_ip_addresses) as agent_ip_addresses_arr,
       values(actor_primary_username) as actor_primary_username_arr,
       values(actor_process_image_name) as actor_process_image_name_arr,
       latest(_time) as _time
  by agent_hostname, action_registry_key_name
| alter display_name = arrayindex(display_name_arr, 0),
        install_location = arrayindex(install_location_arr, 0),
        agent_ip_addresses = arrayindex(agent_ip_addresses_arr, 0),
        actor_primary_username = arrayindex(actor_primary_username_arr, 0),
        actor_process_image_name = arrayindex(actor_process_image_name_arr, 0)
| alter _time = format_timestamp("%Y-%m-%d %H:%M:%S", _time, "Asia/Seoul")
| fields _time, agent_hostname, agent_ip_addresses, actor_process_image_name,
         action_registry_key_name, display_name, install_location, actor_primary_username
| sort desc _time
"""

TIMEFRAME_MS = 86400000     # 24시간 = 86400000
                            #  7일   = 7  * 86400000
                            # 30일   = 30 * 86400000


# ============================================================
# dict -> utf-8 bytes (requests data= 전용)
# ============================================================
def to_bytes(obj):
    text = json.dumps(obj, ensure_ascii=False)
    if isinstance(text, text_type):
        return text.encode("utf-8")
    return text


# ============================================================
# 안전한 출력
# ============================================================
def safe_print(msg):
    if not isinstance(msg, text_type):
        msg = msg.decode("utf-8", errors="replace")
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    line = msg.encode(encoding, errors="replace").decode(encoding)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


# ============================================================
# gzip 해제 (2.7.5 호환)
# ============================================================
def decompress_gzip(data):
    buf = io.BytesIO(data)
    f = gzip.GzipFile(fileobj=buf)
    try:
        result = f.read()
    except Exception:
        result = data
    finally:
        f.close()
    return result

# ============================================================
# 시간 변환
# ============================================================
def convert_timestamps(data_list):
    for row in data_list:
        for key in ("_time", "insert_timestamp"):
            if key in row and isinstance(row[key], (int, float)):
                ts  = row[key] / 1000.0
                kst = datetime.datetime.utcfromtimestamp(ts) + datetime.timedelta(hours=9)
                row[key] = kst.strftime("%Y-%m-%d %H:%M:%S")
    return data_list

# ============================================================
# 파일 저장
# ============================================================
def save_result(obj, path):
    # 1순위: dict/list -> JSON 직렬화
    if isinstance(obj, (dict, list)):
        text = json.dumps(obj, ensure_ascii=False, indent=2)
        if not isinstance(text, text_type):
            text = text.decode("utf-8")
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(text)

    # 2순위: unicode 문자열
    elif isinstance(obj, text_type):
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(obj)

    # 3순위: bytes / bytearray
    elif isinstance(obj, (bytes, bytearray)):
        try:
            text = obj.decode("utf-8")
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(text)
        except UnicodeDecodeError:
            with open(path, "wb") as f:
                f.write(obj)

    else:
        raise TypeError("저장 불가 타입: {0}".format(type(obj)))


# ============================================================
# 1) start_xql_query
# ============================================================
def start_query():
    url  = "{0}/xql/start_xql_query/".format(BASE_URL)
    body = {
        "request_data": {
            "query":     XQL_QUERY,
            "timeframe": {"relativeTime": TIMEFRAME_MS},
        }
    }
    try:
        r = requests.post(url, headers=HEADERS, data=to_bytes(body), timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError("start_query HTTP 오류: {0}".format(str(e)))

    resp = json.loads(r.content.decode("utf-8"))
    execution_id = resp.get("reply")

    if not execution_id:
        raise RuntimeError("execution_id 없음: {0}".format(resp))
    if not isinstance(execution_id, (str, text_type)):
        raise RuntimeError("execution_id 타입 오류: {0}".format(type(execution_id)))

    return execution_id


# ============================================================
# 2) get_query_results
# ============================================================
def get_results(execution_id):
    url  = "{0}/xql/get_query_results/".format(BASE_URL)
    body = {
        "request_data": {
            "query_id":     execution_id,
            "pending_flag": False,
            "format":       "json",
        }
    }
    try:
        r = requests.post(url, headers=HEADERS, data=to_bytes(body), timeout=60)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError("get_results HTTP 오류: {0}".format(str(e)))

    resp  = json.loads(r.content.decode("utf-8"))
    reply = resp.get("reply")

    if not isinstance(reply, dict):
        raise RuntimeError("reply 형식 오류: {0}".format(resp))

    return reply


# ============================================================
# 3) get_query_results_stream
# ============================================================
def get_stream(stream_id):
    url  = "{0}/xql/get_query_results_stream".format(BASE_URL)
    body = {
        "request_data": {
            "stream_id":          stream_id,
            "is_gzip_compressed": True,
        }
    }
    try:
        r = requests.post(
            url,
            headers=HEADERS,
            data=to_bytes(body),
            timeout=600,
            stream=True
        )
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError("get_stream HTTP 오류: {0}".format(str(e)))

    chunks = []
    try:
        for chunk in r.iter_content(chunk_size=65536):
            if chunk:
                chunks.append(chunk)
    except Exception as e:
        raise RuntimeError("stream 수신 오류: {0}".format(str(e)))

    if not chunks:
        raise RuntimeError("stream 데이터 없음")

    raw = b"".join(chunks)
    return decompress_gzip(raw)


# ============================================================
# 메인 오케스트레이션
# ============================================================
def main():
    # 1) 쿼리 시작
    execution_id = start_query()
    safe_print(u"[OK] execution_id = {0}".format(execution_id))

    # 2) 결과 폴링
    elapsed = 0
    reply   = {}

    while True:
        reply  = get_results(execution_id)
        status = reply.get("status")

        if status == "SUCCESS":
            safe_print(u"[OK] 쿼리 완료")
            break

        if status in ("FAIL", "FAILED", "ERROR"):
            raise RuntimeError(u"쿼리 실패: {0}".format(reply))

        safe_print(u"[..] status={0} ({1}s 경과)".format(status, elapsed))
        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC

        if elapsed >= POLL_TIMEOUT_SEC:
            raise Exception(u"폴링 타임아웃 ({0}s)".format(POLL_TIMEOUT_SEC))

    # 3) 건수 확인 → 분기
    total = reply.get("number_of_results", 0)
    safe_print(u"[OK] 결과 건수 = {0}".format(total))

    if total < RESULT_LIMIT:
        data_list = reply.get("results", {}).get("data", [])
        if isinstance(data_list, list):
            convert_timestamps(data_list)
        save_result(reply, OUTPUT_FILE)
        safe_print(u"[OK] 1000건 미만 -> {0} 저장 완료".format(OUTPUT_FILE))
        return

    # 1000건 이상 — stream_id 추출 → stream API 호출 → 저장
    stream_id = reply.get("stream_id")
    if not stream_id:
        results_field = reply.get("results")
        if isinstance(results_field, dict):
            stream_id = results_field.get("stream_id")

    if not stream_id:
        raise RuntimeError(u"stream_id 없음: {0}".format(reply))

    safe_print(u"[OK] 1000건 이상 -> stream_id = {0}".format(stream_id))

    decompressed = get_stream(stream_id)
    try:
        text = decompressed.decode("utf-8")
        # NDJSON(한 줄 = JSON 1건) 파싱
        lines = [l for l in text.splitlines() if l.strip()]
        data_list = [json.loads(l) for l in lines]
        convert_timestamps(data_list)
        save_result(data_list, OUTPUT_FILE)
    except (ValueError, UnicodeDecodeError) as e:
        safe_print(u"[경고] JSON 파싱 실패 ({0}) -> 변환 없이 저장".format(e))
        save_result(decompressed, OUTPUT_FILE)
    safe_print(u"[OK] 저장 완료 -> {0} ({1} bytes)".format(
        OUTPUT_FILE, len(decompressed)))

if __name__ == "__main__":
    main()
