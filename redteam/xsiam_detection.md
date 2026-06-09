# Cortex XDR/XSIAM 탐지 결과 및 XQL 쿼리

> **환경**: Palo Alto Cortex XDR · XSIAM 연동  
> **에이전트**: Ubuntu 22.04, Windows 10/11 양쪽 설치

---

## 📊 전체 탐지 통계

| 분류 | Ubuntu | Windows | 합계 |
|------|--------|---------|------|
| 탐지된 공격 수 | 8/10 | 9/11 | 17/21 |
| 차단(BLOCK) | 5 | 6 | 11 |
| 알림(ALERT) | 3 | 3 | 6 |
| 미탐(MISS) | 2 | 2 | 4 |

---

## 🚨 주요 Alert 목록

### Ubuntu

| Alert ID | 심각도 | MITRE | 설명 |
|----------|--------|-------|------|
| UBNT-001 | HIGH | T1110.001 | SSH Brute Force — 10회 이상 로그인 실패 탐지 |
| UBNT-002 | CRITICAL | T1548.001 | SUID bash 실행 — /bin/bash -p 탐지 |
| UBNT-003 | HIGH | T1003.008 | /etc/shadow 직접 접근 탐지 |
| UBNT-004 | CRITICAL | T1053.003 | /etc/crontab 수정 탐지 |
| UBNT-005 | HIGH | T1059.004 | /dev/tcp 리버스쉘 탐지 |
| UBNT-006 | MEDIUM | T1005 | 대량 파일 아카이빙 탐지 (tar) |
| UBNT-007 | HIGH | T1098.004 | authorized_keys 수정 탐지 |
| UBNT-008 | LOW | T1218 | find를 이용한 대량 파일 접근 |

### Windows

| Alert ID | 심각도 | MITRE | 설명 |
|----------|--------|-------|------|
| WIN-001 | HIGH | T1110.001 | WinRM Brute Force 탐지 |
| WIN-002 | CRITICAL | T1562.001 | AMSI 패치 시도 — AmsiInitFailed 메모리 수정 |
| WIN-003 | CRITICAL | T1003.001 | Mimikatz 시그니처 탐지 |
| WIN-004 | CRITICAL | T1003.001 | LSASS 프로세스 메모리 접근 |
| WIN-005 | HIGH | T1547.001 | Run 레지스트리 키 생성 |
| WIN-006 | HIGH | T1543.003 | 신규 서비스 등록 (BackdoorSvc) |
| WIN-007 | HIGH | T1550.002 | Pass-the-Hash 시도 탐지 |
| WIN-008 | MEDIUM | T1218 | certutil 원격 다운로드 |
| WIN-009 | HIGH | T1059.001 | Encoded PowerShell 명령 실행 |

---

## 🔍 XQL 쿼리 모음

### 1. SSH 브루트포스 탐지

```xql
dataset = xdr_data
| filter event_type = AUTH and agent_os_type = AGENT_OS_LINUX
| filter action_local_port = 22 and action_login_outcome = FAILED
| groupby actor_primary_username, action_remote_ip
| count as fail_count
| filter fail_count >= 10
| sort desc fail_count
```

---

### 2. SUID 바이너리 실행 탐지

```xql
dataset = xdr_data
| filter event_type = PROCESS
| filter actor_process_image_name contains "bash" or actor_process_image_name contains "sh"
| filter actor_process_command_line contains "-p" and agent_os_type = AGENT_OS_LINUX
| fields agent_hostname, actor_process_image_path, actor_process_command_line, event_timestamp
```

---

### 3. /etc/shadow 접근 탐지

```xql
dataset = xdr_data
| filter event_type = FILE
| filter action_file_path = "/etc/shadow"
| fields agent_hostname, actor_process_image_name, actor_effective_username, event_timestamp
| sort desc event_timestamp
```

---

### 4. 리버스쉘 탐지 (bash /dev/tcp)

```xql
dataset = xdr_data
| filter event_type = PROCESS
| filter actor_process_command_line contains "/dev/tcp" or actor_process_command_line contains "nc -e" or actor_process_command_line contains "ncat"
| fields agent_hostname, actor_process_command_line, action_remote_ip, event_timestamp
```

---

### 5. Cron 백도어 탐지

```xql
dataset = xdr_data
| filter event_type = FILE
| filter action_file_path in ("/etc/crontab", "/etc/cron.d/*", "/var/spool/cron/*")
| filter action_file_operation_type in (CREATE, WRITE)
| fields agent_hostname, actor_process_image_name, action_file_path, event_timestamp
```

---

### 6. Mimikatz 탐지 (Windows)

```xql
dataset = xdr_data
| filter event_type = PROCESS and agent_os_type = AGENT_OS_WINDOWS
| filter actor_process_image_name ~= "(?i)(mimikatz|mimi)" or actor_process_command_line ~= "(?i)(sekurlsa|lsadump|privilege::debug)"
| fields agent_hostname, actor_process_image_path, actor_process_command_line, event_timestamp
```

---

### 7. LSASS 접근 탐지

```xql
dataset = xdr_data
| filter event_type = PROCESS and agent_os_type = AGENT_OS_WINDOWS
| filter action_process_image_name = "lsass.exe"
| filter actor_process_image_name not in ("csrss.exe", "wininit.exe", "services.exe", "lsm.exe")
| fields agent_hostname, actor_process_image_name, action_process_image_name, event_timestamp
```

---

### 8. AMSI 우회 탐지

```xql
dataset = xdr_data
| filter event_type = PROCESS and agent_os_type = AGENT_OS_WINDOWS
| filter actor_process_image_name = "powershell.exe"
| filter actor_process_command_line ~= "(?i)(amsi|AmsiUtils|amsiInitFailed)"
| fields agent_hostname, actor_process_command_line, event_timestamp
```

---

### 9. PowerShell 인코딩 명령 탐지

```xql
dataset = xdr_data
| filter event_type = PROCESS and agent_os_type = AGENT_OS_WINDOWS
| filter actor_process_image_name = "powershell.exe"
| filter actor_process_command_line ~= "(?i)(-[Ee]nc|-[Ee]ncodedCommand)"
| fields agent_hostname, actor_process_command_line, event_timestamp
| sort desc event_timestamp
```

---

### 10. certutil 원격 다운로드 탐지

```xql
dataset = xdr_data
| filter event_type = PROCESS and agent_os_type = AGENT_OS_WINDOWS
| filter actor_process_image_name = "certutil.exe"
| filter actor_process_command_line contains "-urlcache" or actor_process_command_line contains "-split"
| fields agent_hostname, actor_process_command_line, action_remote_ip, event_timestamp
```

---

### 11. Pass-the-Hash 탐지

```xql
dataset = xdr_data
| filter event_type = AUTH and agent_os_type = AGENT_OS_WINDOWS
| filter action_login_type = NETWORK
| filter action_login_outcome = SUCCESS
| filter causality_actor_process_image_name in ("psexec.exe", "wmic.exe", "crackmapexec.exe")
| fields agent_hostname, action_remote_ip, actor_primary_username, event_timestamp
```

---

### 12. 레지스트리 Run 키 탐지 (지속성)

```xql
dataset = xdr_data
| filter event_type = REGISTRY and agent_os_type = AGENT_OS_WINDOWS
| filter action_registry_key_name contains "CurrentVersion\\Run"
| filter action_registry_value_name != null
| fields agent_hostname, actor_process_image_name, action_registry_key_name, action_registry_value_data, event_timestamp
```

---

## 📈 탐지 우선순위 권고

| 우선순위 | 이벤트 유형 | 대응 방안 |
|---------|-----------|---------|
| 🔴 CRITICAL | Mimikatz/LSASS 접근 | 즉시 호스트 격리 |
| 🔴 CRITICAL | AMSI 우회 | 즉시 호스트 격리 |
| 🔴 CRITICAL | SUID bash 실행 | 즉시 조사 |
| 🟠 HIGH | 리버스쉘 탐지 | C2 IP 차단 + 격리 |
| 🟠 HIGH | /etc/shadow 접근 | 패스워드 전체 초기화 |
| 🟠 HIGH | 브루트포스 | 소스 IP 차단 |
| 🟡 MEDIUM | certutil/bitsadmin | 프로세스 검토 |
| 🟡 MEDIUM | 대량 파일 접근 | 사용자 행동 분석 |
