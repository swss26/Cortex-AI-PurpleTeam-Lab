# Red Team Exercise — Lab Environment

레드팀 공격 테스트 결과 정리 레포지토리.  
Ubuntu + Windows 혼합 환경에서 수행된 공격 체인, MITRE ATT&CK 매핑, XDR 탐지 결과를 기록합니다.
공격과 방어 양쪽을 **AI(Claude)로 오케스트레이션**한 **AI 기반 퍼플팀** 실습 환경입니다.

---

## 🤖 AI 기반 퍼플팀 자동화 (Red ↔ Blue)

이 랩은 **공격과 방어 양쪽을 AI(Claude)로 오케스트레이션**하는 AI 기반 퍼플팀 환경입니다.
AI가 **MCP(Model Context Protocol)** 를 통해 공격 도구와 보안 플랫폼을 직접 제어합니다.

| 구분 | AI 역할 | 연동 (MCP) |
|------|---------|-----------|
| 🔴 공격 (Red) | 정찰 → 초기 접근 → 실행 → 권한 상승 → 자격증명 → 지속성 → 수집 → 유출 전 단계 자동 수행 | **Kali MCP** |
| 🔵 방어 (Blue) | XDR/XSIAM 로그 조회 → 이벤트 분석 → 인시던트 요약·SOC 리포트 자동 생성 | **Cortex MCP** |

### 🔴 AI 주도 공격 — Kali MCP
- Claude가 Kali MCP를 통해 **Nmap · Hydra · NetExec · Metasploit** 등 공격 도구를 직접 호출
- 공격 체인 전 단계를 자연어 지시로 오케스트레이션 (수동 명령 입력 최소화)
- 각 단계 결과를 판단해 다음 행동을 스스로 선택 (분기 · 재시도)

### 🔵 AI 기반 탐지·분석 — Cortex MCP
- Claude가 Cortex MCP를 통해 **XDR/XSIAM의 엔드포인트 · 알림 · 인시던트 데이터를 조회**
- 수집한 로그를 분석해 공격 체인을 재구성하고 **시니어 SOC 분석가 관점의 리포트**로 요약
- 외부 검색 없이 **에이전트가 수집한 데이터만**으로 탐지 결과 정리

```
[AI 공격 오케스트레이션] --Kali MCP--> [Kali/C2] --공격--> [타겟(XDR Agent)]
                                                                  |
                                                          에이전트 로그·탐지
                                                                  v
[AI 로그 탐지·분석] <--Cortex MCP 로그 조회-- [Cortex XDR / XSIAM]
```

> ⚠️ 모든 AI 자동화는 **격리된 실습 환경**에서만 수행되었으며, 실제 운영 · 고객 환경에는 적용되지 않았습니다.

---

## 📁 구조

```
├── README.md
└── redteam/
    ├── ubuntu_attack_chain.md    # Ubuntu 공격 체인 (30개 기법 + 상세 설명)
    ├── windows_attack_chain.md   # Windows 공격 체인 (38개 기법 + 상세 설명)
    └── xsiam_detection.md        # Cortex XDR/XSIAM 탐지 결과 및 XQL 쿼리
```

---

## 🖥️ 테스트 환경

> ⚠️ **이 환경은 레드팀 테스트를 위해 의도적으로 취약하게 구성된 격리된 랩 환경입니다.**  
> 실제 운영 환경에 이와 같은 설정을 적용해서는 안 됩니다.

| 항목 | 내용 |
|------|------|
| Ubuntu | 14.04 LTS · `<UBUNTU_HOSTNAME>` · `<UBUNTU_IP>` · Cortex XDR 에이전트 설치됨 |
| Windows | 11 · `<WINDOWS_HOSTNAME>` · `<WINDOWS_IP>` · Cortex XDR 에이전트 설치됨 |
| 공격 머신 (Kali) | `<KALI_IP>` |
| Windows C2 서버 | `<C2_IP>` (DNS :53 · HTTP :8080) |
| 보안 솔루션 | Palo Alto Cortex XDR (Ubuntu + Windows 양쪽) |
| 관제 | Cortex XSIAM 연동 |

---

### 🐧 Ubuntu — 취약 환경 구성 및 설치 패키지

공격 시나리오 수행을 위해 아래와 같이 의도적으로 취약한 설정을 적용했습니다.

**취약 설정**

| 설정 | 내용 | 취약한 이유 |
|------|------|-----------|
| SSH 패스워드 인증 허용 | `PasswordAuthentication yes` | 브루트포스 공격 가능 |
| 약한 패스워드 사용 | `sshuser:123`, `webadmin:admin123` | rockyou.txt로 즉시 크랙 |
| SUID bash 설정 | `chmod u+s /bin/bash` | 일반 유저가 root 쉘 획득 가능 |
| sudo 미스컨픽 | `sshuser ALL=(ALL) NOPASSWD: /usr/bin/find` | find로 root 쉘 탈취 가능 |
| /tmp 실행 권한 허용 | `noexec` 미적용 | /tmp에 업로드한 파일 실행 가능 |

**설치 패키지 (공격 대상용)**

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `openssh-server` | 9.6p1 | SSH 브루트포스 / 초기 접근 대상 |
| `python3` | 3.12 | TTY 스폰 (`pty.spawn`) |
| `curl` | 8.x | 페이로드 다운로드 경로 |
| `netcat-openbsd` | 1.219 | 리버스쉘 수신 |
| `cron` | 3.0pl1 | Cron 백도어 등록 대상 |
| `apache2` | 2.4.x | 웹 서비스 (webadmin 계정 연계) |
| `tar`, `find`, `grep` | (기본) | LOLBin 악용 대상 |

---

### 🪟 Windows — 취약 환경 구성 및 설치 패키지

**취약 설정**

| 설정 | 내용 | 취약한 이유 |
|------|------|-----------|
| WinRM 활성화 | `Enable-PSRemoting -Force` | 원격 PowerShell 쉘 접근 가능 |
| 약한 패스워드 사용 | `administrator:Password1!` | 브루트포스로 즉시 획득 |
| PowerShell 실행 정책 완화 | `Set-ExecutionPolicy Unrestricted` | 제한 없이 PS 스크립트 실행 |
| UAC 수준 낮춤 | 알림 없음 수준으로 설정 | UAC 우회 용이 |
| Windows Defender 실시간 보호 해제 | 부분 비활성화 | Mimikatz 등 탐지 우회 |
| SMB 서명 비활성화 | `Set-SmbServerConfiguration -RequireSecuritySignature $false` | NTLM 릴레이 공격 가능 |

**설치 패키지 (공격 도구 — C:\Windows\Temp\)**

| 파일 | 용도 |
|------|------|
| `mimikatz.exe` | 자격증명 덤프 (NTLM 해시, 평문 패스워드) |
| `Invoke-Mimikatz.ps1` | Fileless 버전 Mimikatz (메모리 로드) |
| `procdump.exe` | LSASS 메모리 덤프 |
| `PrintSpoofer.exe` | SeImpersonatePrivilege → SYSTEM 권한 상승 |
| `SharpDPAPI.exe` | 브라우저 저장 패스워드 (DPAPI 복호화) |
| `nc.exe` | Netcat 리버스쉘 |
| `shell.exe` | 지속성용 리버스쉘 바이너리 |

---

## 📋 공격 요약

| 단계 | Ubuntu | Windows |
|------|--------|---------|
| 정찰 | Nmap, 서비스 열거 | Nmap, SMB/WinRM 열거 |
| 초기 접근 | SSH Bruteforce (Hydra) | WinRM Bruteforce / netexec |
| 실행 | Bash 리버스쉘, Cron | PowerShell (AMSI 우회) |
| 권한 상승 | SUID 악용, sudo 미스컨픽 | PrintSpoofer, Token 탈취 |
| 자격증명 | /etc/shadow 덤프, john 크랙 | Mimikatz, LSASS 덤프 |
| 지속성 | Cron 백도어, SSH Key | 레지스트리 Run, 서비스 등록 |
| 수집 | /etc, /home 아카이빙 | SAM 하이브, DPAPI |
| 유출 | SCP, curl HTTP | HTTP POST, DNS |

---

## 🔗 상세 문서

| 문서 | 내용 |
|------|------|
| [Ubuntu 공격 체인](redteam/ubuntu_attack_chain.md) | 30개 기법 · 명령어 상세 · MITRE 매핑 |
| [Windows 공격 체인](redteam/windows_attack_chain.md) | 38개 기법 · 명령어 상세 · MITRE 매핑 |
| [XDR/XSIAM 탐지](redteam/xsiam_detection.md) | Alert 목록 · 탐지 통계 · XQL 쿼리 12개 |
