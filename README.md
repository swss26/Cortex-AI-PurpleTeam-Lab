# RedTeam Exercise — Lab Environment

Palo Alto **Cortex XDR / XSIAM** 기반 **AI 퍼플팀 실습 레포지토리**.
AI(Claude)가 MCP를 통해 공격과 방어를 자동화한 프로젝트들로 구성됩니다.

---

## 📁 프로젝트

| 프로젝트 | 내용 |
|----------|------|
| [🔴🔵 AI 자동화 레드팀 공격·XSIAM 탐지 프로젝트](AI%20%EC%9E%90%EB%8F%99%ED%99%94%20%EB%A0%88%EB%93%9C%ED%8C%80%20%EA%B3%B5%EA%B2%A9%C2%B7XSIAM%20%ED%83%90%EC%A7%80%20%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/README.md) | AI가 **Kali MCP**로 Ubuntu/Windows 침투 자동 수행, **Cortex MCP**로 XSIAM 탐지 이력 조회·분석 |
| [🛡️ 사내 위협행위 대응 프로젝트](%EC%82%AC%EB%82%B4%20%EC%9C%84%ED%98%91%ED%96%89%EC%9C%84%20%EB%8C%80%EC%9D%91%20%ED%94%84%EB%A1%9C%EC%A0%9D%ED%8A%B8/README.md) | 실제 단말 침해사고 IR 분석 (XMRig 크립토마이너 · 다단계 지속성) |

---

## 🤖 공통 컨셉 — AI 기반 퍼플팀 (Red ↔ Blue)

| 구분 | AI 역할 | 연동 (MCP) |
|------|---------|-----------|
| 🔴 공격 | 공격 체인 전 단계 자동 오케스트레이션 | **Kali MCP** |
| 🔵 방어 | XDR/XSIAM 로그 조회 → 분석 → SOC 리포트 | **Cortex MCP** |

> ⚠️ 모든 실습은 **격리된 랩 환경**에서만 수행되었으며, 실제 운영 · 고객 환경에는 적용되지 않았습니다.  
> 내부 IP · 호스트명 · 토큰 등 민감정보는 모두 placeholder로 치환되어 있습니다.
