"""
XSIAM XQL Public API 자동화 - USB 쓰기(외장매체 쓰기) 로그
출력: USB_write_log.json
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

OUTPUT_FILE       = "USB_write_log.json"
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
| filter event_type = FILE
| alter dev_json = to_json_string(action_file_device_info)
| alter drive_type = to_number(json_extract_scalar(dev_json, "$.storage_device_drive_type"))
| alter drive_type = if(drive_type = 2, "이동식(USB 등)",
                   if(drive_type = 3, "로컬 디스크(고정)",
                   if(drive_type = 4, "네트워크 드라이브",
                   if(drive_type = 5, "CD/DVD-ROM",
                   if(drive_type = 6, "RAM 디스크",
                      "기타/알수없음")))))
| filter to_number(json_extract_scalar(dev_json, "$.storage_device_drive_type")) in (2,3,4,5,6)
| filter event_sub_type != FILE_OPEN
| alter _time = format_timestamp("%Y-%m-%d %H:%M:%S", _time, "Asia/Seoul")
| fields _time, event_sub_type, agent_hostname, agent_ip_addresses,
         actor_effective_username, actor_process_command_line, actor_process_image_name,
         action_file_path, action_file_name, drive_type,
         action_device_usb_vendor_name, action_device_usb_product_name, action_device_usb_serial_number
| sort desc _time
"""

TIMEFRAME_MS = 86400000     # 24시간 = 86400000
                            #  7일   = 7  * 86400000
                            # 30일   = 30 * 86400000

# ╚══════════════════════════════════════════════════════════╝


def to_bytes(obj):
    text = json.dumps(obj, ensure_ascii=False)
    if isinstance(text, text_type):
        return text.encode("utf-8")
    return text


def safe_print(msg):
    if not isinstance(msg, text_type):
        msg = msg.decode("utf-8", errors="replace")
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    line = msg.encode(encoding, errors="replace").decode(encoding)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


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


def convert_timestamps(data_list):
    for row in data_list:
        for key in ("_time", "insert_timestamp"):
            if key in row and isinstance(row[key], (int, float)):
                ts  = row[key] / 1000.0
                kst = datetime.datetime.utcfromtimestamp(ts) + datetime.timedelta(hours=9)
                row[key] = kst.strftime("%Y-%m-%d %H:%M:%S")
    return data_list


def save_result(obj, path):
    if isinstance(obj, (dict, list)):
        text = json.dumps(obj, ensure_ascii=False, indent=2)
        if not isinstance(text, text_type):
            text = text.decode("utf-8")
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(text)
    elif isinstance(obj, text_type):
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(obj)
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


def start_query():
    url  = "{0}/xql/start_xql_query/".format(BASE_URL)
    body = {"request_data": {"query": XQL_QUERY, "timeframe": {"relativeTime": TIMEFRAME_MS}}}
    try:
        r = requests.post(url, headers=HEADERS, data=to_bytes(body), timeout=30)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError("start_query HTTP 오류: {0}".format(str(e)))
    resp = json.loads(r.content.decode("utf-8"))
    execution_id = resp.get("reply")
    if not execution_id:
        raise RuntimeError("execution_id 없음: {0}".format(resp))
    return execution_id


def get_results(execution_id):
    url  = "{0}/xql/get_query_results/".format(BASE_URL)
    body = {"request_data": {"query_id": execution_id, "pending_flag": False, "format": "json"}}
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


def get_stream(stream_id):
    url  = "{0}/xql/get_query_results_stream".format(BASE_URL)
    body = {"request_data": {"stream_id": stream_id, "is_gzip_compressed": True}}
    try:
        r = requests.post(url, headers=HEADERS, data=to_bytes(body), timeout=600, stream=True)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError("get_stream HTTP 오류: {0}".format(str(e)))
    chunks = []
    for chunk in r.iter_content(chunk_size=65536):
        if chunk:
            chunks.append(chunk)
    if not chunks:
        raise RuntimeError("stream 데이터 없음")
    return decompress_gzip(b"".join(chunks))


def main():
    execution_id = start_query()
    safe_print(u"[OK] execution_id = {0}".format(execution_id))

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

    total = reply.get("number_of_results", 0)
    safe_print(u"[OK] 결과 건수 = {0}".format(total))

    if total < RESULT_LIMIT:
        data_list = reply.get("results", {}).get("data", [])
        if isinstance(data_list, list):
            convert_timestamps(data_list)
        save_result(reply, OUTPUT_FILE)
        safe_print(u"[OK] 1000건 미만 -> {0} 저장 완료".format(OUTPUT_FILE))
        return

    stream_id = reply.get("stream_id") or reply.get("results", {}).get("stream_id")
    if not stream_id:
        raise RuntimeError(u"stream_id 없음: {0}".format(reply))
    safe_print(u"[OK] 1000건 이상 -> stream_id = {0}".format(stream_id))

    decompressed = get_stream(stream_id)
    try:
        lines = [l for l in decompressed.decode("utf-8").splitlines() if l.strip()]
        data_list = [json.loads(l) for l in lines]
        convert_timestamps(data_list)
        save_result(data_list, OUTPUT_FILE)
    except (ValueError, UnicodeDecodeError) as e:
        safe_print(u"[경고] JSON 파싱 실패 ({0}) -> 변환 없이 저장".format(e))
        save_result(decompressed, OUTPUT_FILE)
    safe_print(u"[OK] 저장 완료 -> {0} ({1} bytes)".format(OUTPUT_FILE, len(decompressed)))

if __name__ == "__main__":
    main()
