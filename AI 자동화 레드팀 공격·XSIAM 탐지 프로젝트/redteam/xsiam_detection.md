# Cortex XDR/XSIAM 탐지 결과 및 XQL 쿼리

> **환경**: Palo Alto Cortex XDR · XSIAM 연동  
> **에이전트**: Ubuntu 14.04 (<UBUNTU_HOSTNAME>), Windows 11 (<WINDOWS_HOSTNAME>) 양쪽 설치  
> **테스트 일자**: 2026-06

---

## 📊 전체 탐지 통계 (실제 테스트 결과)

| 분류 | Ubuntu | Windows |
|------|--------|---------|
| XSIAM 알림(Alert) 수 | 1 | 54 |
| XSIAM Case | Incident #266, #972, #1623 | **Case #272** (111 issues, score 97/100) |
| 실제 차단(PREVENT) | 0 | 3 (SAM dump, LSA secrets, DNS C2) |
| Case 상태 | resolved_true_positive | resolved_true_positive |

> **Windows Case #272**: "SYNC - Credential Gathering" 외 110개 이슈  
> MITRE 커버리지: T1003.001/002, T1059.001, T1218.005/010/011, T1053, T1021, T1134

---

## 🚨 주요 Alert 목록

### Ubuntu (Incident #266, #972, #1623 — <UBUNTU_HOSTNAME>)

| 인시던트 | 심각도 | MITRE | 설명 |
|----------|--------|-------|------|
| #266 | HIGH | T1059.004, T1003.008, T1574, T1190 | Local Threat Detected — www-data 통한 초기접근, /etc/shadow 접근 |
| #972 | HIGH | T1059.004, T1574.006, T1072 | Script Activity — Unix Shell 실행, Dynamic Linker Hijacking |
| #1623 | HIGH | T1059, T1053.003, T1574.006 | Local Analysis Malware — Cron 백도어, LD_PRELOAD |

### Windows (Case #272 — <WINDOWS_HOSTNAME>, 111 issues)

| 탐지 범주 | MITRE | 설명 |
|----------|-------|------|
| Credential Access | T1003.001/002/004/005 | SAM 하이브 덤프 · LSA Secrets · LSASS 접근 (일부 차단) |
| Execution | T1059.001, T1569.002 | PowerShell AMSI 우회 · 서비스 실행 |
| Defense Evasion | T1218.005/010/011 | mshta · regsvr32 · rundll32 (Squiblydoo) |
| Persistence | T1053, T1547, T1543 | 스케줄 태스크 · Run 키 · 서비스 등록 · WMI 이벤트 |
| Lateral Movement | T1021.002, T1550.002 | SMB/WinRM · Pass-the-Hash |
| C2 / Exfil | T1102.002, T1048 | DNS 터널링 (telemetry.windows-cdn.net) · HTTP POST |

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
