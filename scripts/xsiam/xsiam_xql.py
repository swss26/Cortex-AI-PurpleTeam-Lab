"""
XSIAM XQL Public API 자동화
  ① start_xql_query           → execution_id
  ② get_query_results         → 결과 (1000건 미만이면 그대로 저장)
  ③ get_query_results_stream  → stream_id 로 대용량 결과 받아서 저장 (gunzip × 2)
출력: results.json
"""

import json
import gzip
import time
import requests


# ============================================================
# 환경 설정 (API Key / FQDN / Auth ID)
# ============================================================
BASE_URL  = "https://api-skiens.xdr.sg.paloaltonetworks.com/public_api/v1"
AUTH_KEY  = "IUKj5ffcEksaZLhu613P0S9xwO8vyo3gCv2iMl33BNsKsmgnw8jbLMqINLXesMpC0Bsbig7obf1JVRSxPTMXUcGVTpjX4f85psuUSWcVfKwnCXdRs9p1BnbGlSNrwX0P"
AUTH_ID   = "6"

HEADERS = {
    "x-xdr-auth-id": AUTH_ID,
    "Authorization": AUTH_KEY,
    "Content-Type":  "application/json",
}

OUTPUT_FILE       = "results.json"
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
       values(event_type) as event_type_arr,
       values(event_sub_type) as event_sub_type_arr,
       latest(_time) as _time
  by agent_hostname, action_registry_key_name
| alter display_name = arrayindex(display_name_arr, 0),
        install_location = arrayindex(install_location_arr, 0),
        agent_ip_addresses = arrayindex(agent_ip_addresses_arr, 0),
        actor_primary_username = arrayindex(actor_primary_username_arr, 0),
        actor_process_image_name = arrayindex(actor_process_image_name_arr, 0),
        event_type = arrayindex(event_type_arr, 0),
        event_sub_type = arrayindex(event_sub_type_arr, 0)
| alter _time_readable = format_timestamp("%Y-%m-%d %H:%M:%S", _time, "Asia/Seoul")
| fields _time,
         _time_readable,
         agent_hostname,
         agent_ip_addresses,
         actor_process_image_name,
         action_registry_key_name,
         display_name,
         install_location,
         actor_primary_username,
         event_type,
         event_sub_type
| sort desc _time
"""

TIMEFRAME_MS = 86400000     # 24시간 = 86400000
                            #  7일   = 7  * 86400000
                            # 30일   = 30 * 86400000

# ╚══════════════════════════════════════════════════════════╝


# ============================================================
# ①  start_xql_query  — 쿼리 시작
# ============================================================
def start_query() -> str:
    url  = f"{BASE_URL}/xql/start_xql_query/"
    body = {
        "request_data": {
            "query": XQL_QUERY,
            "timeframe": {"relativeTime": TIMEFRAME_MS},
        }
    }
    r = requests.post(url, headers=HEADERS, json=body, timeout=30)
    r.raise_for_status()
    return r.json()["reply"]


# ============================================================
# ②  get_query_results  — 결과 조회 (폴링용)
# ============================================================
def get_results(execution_id: str) -> dict:
    url  = f"{BASE_URL}/xql/get_query_results/"
    body = {
        "request_data": {
            "query_id":     execution_id,
            "pending_flag": False,
            "format":       "json",
        }
    }
    r = requests.post(url, headers=HEADERS, json=body, timeout=60)
    r.raise_for_status()
    return r.json()["reply"]


# ============================================================
# ③  get_query_results_stream — 대용량(1000건 이상) 결과 받기
#    응답이 gzip × 2 라서 두 번 풀어야 함
#    (HTTP transport gzip 은 requests 가 자동으로 푸므로,
#     우리가 한 번만 더 gzip.decompress 해주면 됨)
# ============================================================
def get_stream(stream_id: str) -> bytes:
    url  = f"{BASE_URL}/xql/get_query_results_stream"
    body = {
        "request_data": {
            "stream_id":           stream_id,
            "is_gzip_compressed":  True,
        }
    }
    headers = {**HEADERS, "Accept-Encoding": "gzip"}
    r = requests.post(url, headers=headers, json=body, timeout=600)
    r.raise_for_status()
    return gzip.decompress(r.content)        # body 측 gzip 풀기


# ============================================================
# 파일 저장
# ============================================================
def save_json(obj_or_text, path: str) -> None:
    if isinstance(obj_or_text, (bytes, bytearray)):
        with open(path, "wb") as f:
            f.write(obj_or_text)
    elif isinstance(obj_or_text, str):
        with open(path, "w", encoding="utf-8") as f:
            f.write(obj_or_text)
    else:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj_or_text, f, ensure_ascii=False, indent=2)


# ============================================================
# 메인 오케스트레이션
# ============================================================
def main() -> None:
    # 1) 쿼리 시작
    execution_id = start_query()
    print(f"[OK] execution_id = {execution_id}")

    # 2) 결과 폴링
    elapsed = 0
    while True:
        reply = get_results(execution_id)
        status = reply.get("status")
        if status == "SUCCESS":
            break
        if status in ("FAIL", "FAILED", "ERROR"):
            raise RuntimeError(f"쿼리 실패: {reply}")
        if elapsed >= POLL_TIMEOUT_SEC:
            raise TimeoutError(f"폴링 타임아웃 ({POLL_TIMEOUT_SEC}s)")
        print(f"[..] status={status} ({elapsed}s)")
        time.sleep(POLL_INTERVAL_SEC)
        elapsed += POLL_INTERVAL_SEC

    # 3) 건수 확인 → 분기
    total = reply.get("number_of_results", 0)
    print(f"[OK] 결과 건수 = {total}")

    if total < RESULT_LIMIT:
        # 1000건 미만 — 응답 자체에 데이터가 있으므로 그대로 저장
        save_json(reply, OUTPUT_FILE)
        print(f"[OK] 1000건 미만 → {OUTPUT_FILE} 저장 완료")
        return

    # 1000건 이상 — stream_id 추출 → stream API 호출 → 저장
    stream_id = (
        reply.get("stream_id")
        or reply.get("results", {}).get("stream_id")
    )
    if not stream_id:
        raise RuntimeError(f"stream_id 가 응답에 없습니다: {reply}")
    print(f"[OK] 1000건 이상 → stream_id = {stream_id}")

    decompressed = get_stream(stream_id)
    save_json(decompressed, OUTPUT_FILE)
    print(f"[OK] stream 결과 → {OUTPUT_FILE} 저장 완료 ({len(decompressed)} bytes)")


if __name__ == "__main__":
    main()
