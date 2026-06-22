# XSIAM Forensics 수집 · XQL 쿼리 · 탐지 결과 · 대응

> **환경**: Palo Alto Cortex XDR · XSIAM 연동  
> **대상**: 김차장 PC · Windows 11 · `<VICTIM_IP>`  
> **수집 방식**: Cortex XDR Forensics Triage Collection (11,170건)  
> **분석 기간**: 2026-06-18 ~ 2026-06-19

---

## 📊 수집 개요

XDR 에이전트가 초기 감염 구간(~13:03–14:04 KST)에 오프라인이었으므로 실시간 `xdr_data` 텔레메트리가 부재했다. 대신 **Forensics Triage Collection**으로 디스크 아티팩트를 수집하여 사후 재구성했다.

| 항목 | 값 |
|------|-----|
| 총 수집 건수 | 11,170건 |
| 수집 완료 | 2026-06-18 ~16:55 KST |
| investigation_id | `<INVESTIGATION_ID>` |
| collection_id | `<COLLECTION_ID>` |
| agent_id | `<AGENT_ID>` |

### 활용 Forensics 데이터셋

| 데이터셋 | 용도 | 핵심 발견 |
|----------|------|----------|
| `forensics_prefetch` | 실행 파일 흔적 | `SVCHOST.EXE-2A35E6EF.pf` (위장 svchost 확정) |
| `forensics_background_activity_monitor` | 앱 최종 실행 시각(BAM) | `Hwp.exe` 13:03 KST |
| `forensics_recent_files` | 최근 파일/LNK | ms-gamingoverlay LNK 2건, 파일.lnk |
| `forensics_scheduled_tasks` | 스케줄드 태스크 | CriticalUpdate(LUR), GoogleUpdateTaskSYSTEM |
| `forensics_amcache` | 설치/실행 메타데이터 | KB5019959.exe SHA1 |
| `forensics_bodyfile` | 파일시스템 타임라인 | C:\ProgramData\Google 생성 시각 |

> ⚠️ **트러블슈팅**: `forensics_prefetch` / `forensics_bodyfile`는 **명시적 시간 범위(from/to)** 없이 조회 시 500 에러 발생. 모든 쿼리에 날짜 범위 필수 지정.

---

## 🔍 XQL 쿼리 모음

### 1. 위장 svchost.exe 탐지 (Prefetch)

```xql
dataset = forensics_prefetch
| filter executable_name = "SVCHOST.EXE"
| filter target_path = null or target_path = "" or target_path != "C:\Windows\System32\svchost.exe"
| fields executable_name, prefetch_hash, target_path, run_count, last_run_time
| sort desc last_run_time
```
> 정상 svchost는 `System32` 경로 해시를 가진다. 다른 해시(`2A35E6EF`)의 SVCHOST.EXE = 마스커레이딩.

---

### 2. 비정상 경로 PowerShell/svchost 실행 (xdr_data, 재연결 후)

```xql
dataset = xdr_data
| filter event_type = PROCESS and agent_os_type = AGENT_OS_WINDOWS
| filter actor_process_image_name in ("svchost.exe", "KB5019959.exe")
| filter actor_process_image_path not contains "\System32\"
| fields agent_hostname, actor_process_image_path, actor_process_command_line, action_remote_ip, event_timestamp
| sort desc event_timestamp
```

---

### 3. XMRig 마이닝 풀 연결 탐지

```xql
dataset = xdr_data
| filter event_type = NETWORK or event_type = STORY
| filter action_remote_ip = "65.21.239.189" or dst_action_external_hostname = "ssl-maimai.com"
| filter action_remote_port = 27039
| fields agent_hostname, actor_process_image_name, action_remote_ip, action_remote_port, event_timestamp
```

---

### 4. PowerShell EncodedCommand (Base64 페이로드) 탐지

```xql
dataset = xdr_data
| filter event_type = PROCESS and agent_os_type = AGENT_OS_WINDOWS
| filter actor_process_command_line ~= "(?i)(-e |-enc|-encodedcommand)"
| filter actor_process_command_line ~= "(?i)([A-Za-z0-9+/]{100,})"
| fields agent_hostname, actor_process_image_path, actor_process_command_line, event_timestamp
| sort desc event_timestamp
```

---

### 5. Windows Defender 예외 등록 탐지

```xql
dataset = xdr_data
| filter event_type = PROCESS
| filter actor_process_command_line ~= "(?i)(Add-MpPreference|Set-MpPreference)"
| filter actor_process_command_line ~= "(?i)(ExclusionPath|ExclusionProcess)"
| fields agent_hostname, actor_process_command_line, actor_effective_username, event_timestamp
```

---

### 6. 악성 스케줄드 태스크 탐지 (Forensics)

```xql
dataset = forensics_scheduled_tasks
| filter task_name in ("CriticalUpdate(LUR)", "GoogleUpdateTaskSYSTEM")
   or task_name ~= "(?i)UVxOHL"
   or task_command ~= "(?i)(KB5019959|svchost\.exe -e|BitsTransfer)"
| fields task_name, task_path, task_command, task_trigger, author
```

---

### 7. BITS Transfer 다운로드 탐지

```xql
dataset = xdr_data
| filter event_type = PROCESS
| filter actor_process_command_line ~= "(?i)(Start-BitsTransfer|bitsadmin)"
| filter actor_process_command_line ~= "(?i)(googleapis\.com|drive\.google)"
| fields agent_hostname, actor_process_command_line, event_timestamp
```

---

### 8. BAM 기준 의심 실행 파일 (초기 벡터 추적)

```xql
dataset = forensics_background_activity_monitor
| filter last_execution_time between "2026-06-18T03:00:00" and "2026-06-18T05:30:00"
| filter executable_path ~= "(?i)(Hwp\.exe|\.tmp|\\Temp\\|\\Downloads\\)"
| fields user_sid, executable_path, last_execution_time
| sort asc last_execution_time
```
> KST 13:03 = UTC 04:03. `Hwp.exe`가 XMRig 최초 연결 30분 전 실행으로 확인.

---

### 9. 의심 LNK 파일 탐지 (Recent Files)

```xql
dataset = forensics_recent_files
| filter file_name ~= "(?i)(ms-gamingoverlay|\.lnk$)"
| filter target_path = null or target_path = ""
| fields file_name, target_path, created_time, accessed_time
| sort desc created_time
```

---

### 10. C:\ProgramData\Google 스테이징 디렉터리 (Bodyfile 타임라인)

```xql
dataset = forensics_bodyfile
| filter file_path contains "C:\ProgramData\Google"
| filter timestamp between "2026-06-18T03:00:00" and "2026-06-18T08:00:00"
| fields file_path, file_size, created_time, modified_time
| sort asc created_time
```

---

## 🚨 탐지 결과 요약

| 범주 | MITRE | 탐지/차단 | 비고 |
|------|-------|-----------|------|
| Masquerading | T1036.005 | 사후 탐지 | XDR 오프라인 중 실행, Prefetch로 확인 |
| Impair Defenses | T1562.001 | 사후 탐지 | 재연결 후 버퍼 이벤트 수신 |
| Scheduled Task | T1053.005 | **PREVENT** | CriticalUpdate(LUR) 반복 차단 |
| Resource Hijacking | T1496 | 사후 탐지 | 마이닝 풀 연결 확인 |
| BITS Jobs / C2 | T1197/T1105 | 사후 탐지 | Google Drive 다운로더 디코딩 |

> XDR가 스케줄드 태스크는 차단(PREVENT)했으나 자기복구 루프로 반복 재시도됨. 초기 실행 구간은 오프라인으로 실시간 차단 부재.

---

## 🧬 IOC 전체 목록 (14개)

| 분류 | 값 | 심각도 | 비고 |
|------|-----|--------|------|
| Hash (SHA1) | `0b2e795525166044e6c2b8527b5f01571b4e6718` | Critical | svchost.exe = KB5019959.exe (32비트 powershell) |
| IP:Port | `65.21.239.189:27039` | Critical | XMRig Monero 마이닝 풀 |
| Domain | `ssl-maimai.com` | Critical | 마이닝 풀 도메인 (ssl:// 27039) |
| Wallet ID | `43b1fdda-f121-4f80-8832-ff29b7007739` | High | XMRig --user 인수 |
| File Path | `C:\Windows\svchost.exe` | Critical | System32 외 경로 — 마스커레이딩 |
| File Path | `C:\ProgramData\KB5019959.exe` | Critical | KB 패치 위장 powershell |
| File Path | `C:\ProgramData\Google\7z.exe` | High | 공격자 스테이징 7-Zip |
| File Path | `C:\ProgramData\Google\.png.001` | High | PNG 위장 7z 아카이브 |
| Google Drive ID | `1FIdeFWuXuwHgvxy1c3q6Xv2BFYaKMS0O` | Critical | 페이로드 배포 파일 |
| Google API Key | `AIzaSyD94KbMUwXmWDriqj2UQGL_TRXNg51y1q8` | High | BITS Transfer 사용 키 |
| Task Path | `\Microsoft\Windows\Google\GoogleUpdateTaskSYSTEM` | Critical | 다운로더 태스크 |
| Task Name | `CriticalUpdate(LUR)` | Critical | 30분 자기복구 태스크 |
| Task Path | `\Microsoft\Windows\UVxOHL_10240...` | High | 최종 페이로드 태스크 (미확인) |
| Network Share | `\\<FILESERVER_IP>\gt00\` | High | PPTX 수신 공유, 초기 유입 후보 |

---

## 🛠️ 대응 권고

### 🔴 즉시 (0–1시간)

1. **단말 격리** — XSIAM `isolate_endpoint` 실행. `UVxOHL_10240` 최종 페이로드 목적 확인 전까지 격리 유지.
2. **Google Drive 신고** — File ID `1FIdeFWuXuwHgvxy1c3q6Xv2BFYaKMS0O` 및 API Key `AIzaSyD94KbMUwXmWDriqj2UQGL_TRXNg51y1q8` Google Trust & Safety 신고 및 차단.
3. **IOC 등록** — SHA1 / `ssl-maimai.com` / `65.21.239.189` XSIAM Threat Intel(`insert_iocs`) 등록 후 전사 스캔.

### 🟠 당일 (1–8시간)

4. **`<FILESERVER_IP>` 공유 서버 조사** — `\\<FILESERVER_IP>\gt00\` PPTX 해시 확인 및 Forensics 수집. 동일 공유 접근 사용자 전원 식별.
5. **`C:\ProgramData\Google` 분석** — 격리 후 7z 비밀번호 추출 및 `.png.001` 압축 해제 내용 확인. `UVxOHL_10240` 태스크 XML 수동 추출.

### 🟡 48시간 이내

6. **HWP 악성 문서 추적** — `forensics_recent_files` 전체 조회로 HWP 경로 확인. 존재 시 OLE 객체 분석 및 악성 판정.
7. **ms-gamingoverlay LNK 분석** — LNK hex 분석으로 실제 target 확인. 동일 LNK가 타 단말에 존재하는지 전사 Forensics 확인.
8. **XDR 오프라인 원인 조사** — 공격자의 의도적 에이전트 종료 여부 확인. Windows 이벤트 로그(서비스 중단) 점검.

---

## 검증 스크립트 (Base64 페이로드 디코딩)

```python
#!/usr/bin/env python3
# PowerShell -EncodedCommand 다단계 디코딩
import base64

def decode_layer(b64: str) -> str:
    return base64.b64decode(b64).decode('utf-16-le')

# Layer1 → Layer2 → Layer3 순차 디코딩
layer1 = decode_layer(LAYER1_B64)   # svchost 복사 + Layer2
layer2 = decode_layer(LAYER2_B64)   # Add-MpPreference (Defender 예외)
layer3 = decode_layer(LAYER3_B64)   # BitsTransfer + 7z + ScheduledTask
print(layer1, layer2, layer3, sep="\n---\n")
```

---

*분석: Tier 3 위협 분석팀 / 분류: 내부 기밀 / 2026-06-19*
