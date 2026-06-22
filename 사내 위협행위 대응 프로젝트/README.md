# 사내 위협행위 대응 프로젝트 — XMRig 크립토마이너 침해사고

실제 사내 단말에서 발생한 침해사고에 대한 **Cortex XDR/XSIAM Forensics 기반 사후 분석(IR)** 기록.  
김차장 PC(Windows 11)에서 탐지된 XMRig 크립토마이너 및 다단계 지속성 메커니즘의 전체 공격 체인을 재구성하고, MITRE ATT&CK 매핑·IOC·대응 권고를 정리합니다.

---

## ⚠️ 업로드 전 필수 확인 사항

**아래 항목은 공개 레포에 절대 포함하지 않는다.** (사내 실제 침해 데이터)

| 항목 | 예시 | 대체 표현 |
|------|------|----------|
| 피해 단말 IP | `172.16.x.x` | `<VICTIM_IP>`, `<FILESERVER_IP>` |
| 사용자 ID | 실제 사번/계정 | `<VICTIM_USER>` |
| XDR 식별자 | agent/investigation/collection ID | `<AGENT_ID>` 등 |
| XSIAM 테넌트 URL | `api-xxx.xdr.*.paloaltonetworks.com` | `<XSIAM_API_URL>` |

> C2 인프라(마이닝 풀 IP/도메인, Google Drive File ID 등)는 **위협 인텔리전스 공유 목적**으로 유지한다.

---

## 📁 구조

```
사내 위협행위 대응 프로젝트/
├── README.md                      # 사고 개요·범위·타임라인·IOC 요약 (본 문서)
└── analysis/
    ├── attack_chain.md            # 다단계 공격 체인 기법별 상세 + 페이로드 디코딩
    └── forensics_detection.md     # XSIAM Forensics 수집·XQL 쿼리·탐지 결과·대응
```

---

## 🧾 사고 개요

| 항목 | 내용 |
|------|------|
| 사고 유형 | 단말 침해 / XMRig Monero 크립토마이닝 + 다단계 지속성 |
| 심각도 | **Critical** |
| 대상 | 김차장 PC · Windows 11 · `<VICTIM_IP>` · 사용자 `<VICTIM_USER>` |
| 사고 발생 | 2026-06-18 |
| 분석 완료 | 2026-06-19 |
| 분석 등급 | Tier 3 |
| 최초 C2 통신 | 2026-06-18 13:33 KST |
| XDR 재연결 | 2026-06-18 14:04 KST |
| Forensics 수집 | 11,170건 |
| 확인 IOC | 14개 |

2026년 6월 18일, 김차장 단말에서 XMRig 기반 Monero 크립토마이너가 탐지됐다. Cortex XDR는 반복 스케줄드 태스크를 차단했으나, 초기 실행 구간(XDR 오프라인, ~13:03–14:04 KST)의 실시간 텔레메트리는 부재했다. **Forensics 수집 데이터(11,170건)의 사후 재구성**으로 전체 공격 체인을 확인했다.

공격자는 단순 마이너 설치를 넘어 **Defender 예외 등록 · Google Drive 페이로드 다운로더 · 자기복구 루프 · 3중 Base64 인코딩**을 포함한 지속적 C2 인프라를 구축했다. 숙련된 위협 행위자의 작업 패턴이다.

---

## 🔗 공격 흐름 요약

```
[초기 유입]     Hwp.exe / 네트워크 공유 PPTX (벡터 미확정, XDR 오프라인)
    │
    ▼
[마스커레이딩]  powershell.exe → C:\Windows\svchost.exe / C:\ProgramData\KB5019959.exe
    │
    ▼
[방어 회피]     Windows Defender ExclusionPath/Process 등록 + 3중 Base64 인코딩
    │
    ▼
[실행]          svchost.exe(위장 powershell) → XMRig rx/0 → ssl-maimai.com:27039
    │
    ▼
[지속성]        CriticalUpdate(LUR) 30분 자기복구 + GoogleUpdateTaskSYSTEM 다운로더
    │
    ▼
[추가 페이로드] Google Drive → .png.001(7z) → 7z.exe 해제 → UVxOHL_10240 (미확인)
```

> 단계별 상세 분석: [analysis/attack_chain.md](analysis/attack_chain.md)

---

## ⏱️ 타임라인 요약 (KST, 2026-06-18)

| 시각 | 이벤트 | MITRE |
|------|--------|-------|
| ~13:03 | `Hwp.exe`(한글 2024) 마지막 실행 — BAM 기록. 최초 유입 벡터 유력 후보 | T1204.002 |
| ~13:33 | `C:\Windows\svchost.exe` → `65.21.239.189:27039` XMRig 최초 연결 | T1496 |
| ~14:04 | XDR 에이전트 재연결 → 버퍼 이벤트 일괄 업로드 (Defender 예외 수신) | T1562.001 |
| ~14:47 | CriticalUpdate(LUR) 자기복구 루프 → `KB5019959.exe` 생성 | T1053.005 |
| 14:51 | `ms-gamingoverlay---.lnk` 외 1건 생성 (target 없음, 1초 간격) | T1547 |
| ~15:33 | SYSTEM 계정 Desktop 경로 접근 (`파일.lnk`) | T1083 |
| ~16:55 | Cortex XDR Forensics 수집 완료 (11,170건) | — |

---

## 🎯 MITRE ATT&CK 매핑 요약

| 전술 | 기법 |
|------|------|
| Initial Access | T1204.002 User Execution |
| Defense Evasion | T1036.005 Masquerading · T1562.001 Impair Defenses · T1027 Obfuscation · T1140 Deobfuscate · T1218 LOLBAS |
| Execution | T1059.001 PowerShell |
| Persistence | T1053.005 Scheduled Task · T1547 Autostart |
| Command & Control | T1105 Ingress Tool Transfer · T1197 BITS Jobs |
| Impact | T1496 Resource Hijacking |
| Discovery | T1083 File and Directory Discovery |

---

## 🧬 IOC 요약

| 분류 | 값 | 심각도 |
|------|-----|--------|
| SHA1 | `0b2e795525166044e6c2b8527b5f01571b4e6718` | Critical |
| IP:Port | `65.21.239.189:27039` | Critical |
| Domain | `ssl-maimai.com` | Critical |
| Wallet ID | `43b1fdda-f121-4f80-8832-ff29b7007739` | High |
| Google Drive ID | `1FIdeFWuXuwHgvxy1c3q6Xv2BFYaKMS0O` | Critical |
| Task | `CriticalUpdate(LUR)` / `GoogleUpdateTaskSYSTEM` / `UVxOHL_10240` | Critical |

> 전체 14개 IOC 및 XQL 탐지 쿼리: [analysis/forensics_detection.md](analysis/forensics_detection.md)

---

## ✅ 즉시 조치 권고 (요약)

| 우선순위 | 조치 |
|----------|------|
| 🔴 즉시 | 단말 격리 · Google Drive 파일/API Key 신고 · IOC 전사 등록 및 스캔 |
| 🟠 당일 | `<FILESERVER_IP>` 공유 서버 조사 · `C:\ProgramData\Google` 디렉터리 분석 |
| 🟡 48h | HWP 악성 문서 추적 · ms-gamingoverlay LNK 분석 · XDR 오프라인 원인 조사 |

> 상세 권고: [analysis/forensics_detection.md](analysis/forensics_detection.md#대응-권고)

---

*분석: Tier 3 위협 분석팀 / 2026-06-18 사고 발생 → 2026-06-19 보고서 완료 / 분류: 내부 기밀*
