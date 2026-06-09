# Red Team Exercise — Lab Environment

레드팀 공격 테스트 결과 정리 레포지토리.  
Ubuntu + Windows 혼합 환경에서 수행된 공격 체인, 설치된 공격 도구, MITRE ATT&CK 매핑, XDR 탐지 결과를 기록합니다.

---

## 📁 구조

```
├── README.md
└── redteam/
    ├── ubuntu_attack_chain.md       # Ubuntu 공격 체인 (30개 기법 + MITRE)
    ├── ubuntu_installed_tools.md    # Ubuntu 서버에 설치/투하된 도구 목록
    ├── windows_attack_chain.md      # Windows 공격 체인 (38개 기법 + MITRE)
    ├── windows_installed_tools.md   # Windows 서버에 설치/투하된 도구 목록
    └── xsiam_detection.md           # Cortex XDR/XSIAM 탐지 결과 및 XQL 쿼리
```

---

## 🖥️ 테스트 환경

| 항목 | 내용 |
|------|------|
| Ubuntu | 22.04 LTS · Cortex XDR 에이전트 설치됨 |
| Windows | 10/11 · Cortex XDR 에이전트 설치됨 |
| 공격 머신 | Kali Linux |
| 보안 솔루션 | Palo Alto Cortex XDR (Ubuntu + Windows 양쪽) |
| 관제 | Cortex XSIAM 연동 |

---

## 📋 공격 요약

| 단계 | Ubuntu | Windows |
|------|--------|---------|
| 정찰 | Nmap, 서비스 열거 | Nmap, SMB/WinRM 열거 |
| 초기 접근 | SSH Bruteforce (Hydra) | Evil-WinRM / CrackMapExec |
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
| [Ubuntu 공격 체인](redteam/ubuntu_attack_chain.md) | 단계별 공격 기법, 명령어, MITRE 매핑 |
| [Ubuntu 설치 도구](redteam/ubuntu_installed_tools.md) | 서버에 투하된 파일, 생성된 계정, 수정된 파일 |
| [Windows 공격 체인](redteam/windows_attack_chain.md) | 단계별 공격 기법, 명령어, MITRE 매핑 |
| [Windows 설치 도구](redteam/windows_installed_tools.md) | 서버에 투하된 바이너리, 레지스트리/서비스/스케줄 변경 |
| [XDR/XSIAM 탐지](redteam/xsiam_detection.md) | Alert 목록, 탐지 통계, XQL 쿼리 12개 |
