# Red Team Exercise — Lab Environment

레드팀 공격 테스트 결과 정리 레포지토리.  
Ubuntu + Windows 혼합 환경에서 수행된 공격 체인, MITRE ATT&CK 매핑, XDR 탐지 결과를 기록합니다.

---

## 📁 구조

```
├── redteam/
│   ├── ubuntu_attack_chain.md      # Ubuntu 공격 체인 전체 정리
│   ├── windows_attack_chain.md     # Windows 공격 체인 전체 정리
│   └── xsiam_detection.md          # Cortex XDR/XSIAM 탐지 결과 및 XQL
├── scripts/
│   ├── ppt/                         # 레드팀 보고서 PPT 생성 스크립트
│   │   ├── gen_ppt_v3.py           # 프로세스 트리 시각화 (최신)
│   │   ├── gen_ppt_v2.py           # 테이블 기반 상세 버전
│   │   └── generate_attack_ppt.py  # 초기 다크테마 버전
│   └── xsiam/                       # XSIAM XQL API 자동화 스크립트
│       ├── xsiam_xql.py
│       ├── xsiam_install.py
│       ├── xsiam_adb_log.py
│       ├── xsiam_process_block.py
│       ├── xsiam_usb_write.py
│       └── xsiam_md_to_html.py
```

## 🖥️ 테스트 환경

| 항목 | 내용 |
|------|------|
| Ubuntu | 22.04 LTS · Cortex XDR 에이전트 설치됨 |
| Windows | Windows 10/11 · Cortex XDR 에이전트 설치됨 |
| 보안 솔루션 | Palo Alto Cortex XDR (양쪽 모두) |
| 관제 | Cortex XSIAM 연동 |

## 📋 공격 요약

| 단계 | Ubuntu | Windows |
|------|--------|---------|
| 정찰 | Nmap, 서비스 열거 | Nmap, SMB 열거 |
| 초기 접근 | SSH Bruteforce | WinRM / SMB |
| 실행 | Bash 페이로드, Cron | PowerShell, AMSI Bypass |
| 권한 상승 | SUID, sudo 오용 | Token 탈취, UAC Bypass |
| 자격증명 | /etc/shadow 덤프 | Mimikatz, LSASS 덤프 |
| 지속성 | Cron backdoor, SSH Key | Registry Run, 서비스 등록 |
| C2 | Netcat 리버스쉘 | PowerShell 리버스쉘 |

## 🔗 상세 문서

- [Ubuntu 공격 체인](redteam/ubuntu_attack_chain.md)
- [Windows 공격 체인](redteam/windows_attack_chain.md)
- [XDR/XSIAM 탐지 결과](redteam/xsiam_detection.md)
