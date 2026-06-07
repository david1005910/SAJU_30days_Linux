# 사주공학 — YouTube 자동화 파이프라인

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue.svg)
![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
[![GitHub](https://img.shields.io/badge/GitHub-SAJU__30days__Linux-181717?logo=github)](https://github.com/david1005910/SAJU_30days_Linux)

### "사주를 감(感)이 아닌 데이터로 읽는다"

전통 사주명리학 × Claude AI × 완전 자동화 — 에피소드 한 편을 **$0.05, 버튼 한 번**으로

[빠른 시작](#-빠른-시작) • [아키텍처](#-아키텍처) • [비용 분석](#-실측-비용) • [기여하기](#-기여하기)

</div>

---

## 왜 만들었나

명리학은 수천 년간 축적된 동양의 패턴 데이터베이스입니다.  
그런데 기존 사주 콘텐츠는 대부분 "느낌"으로 해석하고, AI는 그것을 그대로 환각합니다.

이 프로젝트는 다릅니다.

1. **계산은 결정론적** — 만세력 라이브러리(`sxtwl`)로 사주팔자를 수학적으로 산출, SHA-256으로 검증
2. **해석만 AI** — 계산된 사실(일간·오행·십신)만 Claude에게 넘겨 한국어 스크립트 생성
3. **운영은 1클릭** — 대시보드에서 승인 버튼 하나로 영상 제작~업로드 완료

---

## 핵심 수치 (실측)

| 지표 | 값 |
|------|-----|
| 에피소드당 비용 | **$0.048** (Claude API 실측) |
| 30일 전체 비용 | **$1.39** |
| 파이프라인 단계 | **8단계** 완전 자동 |
| 커리큘럼 | **30편** 자동 생성·승인 완료 |
| 검증 방식 | SHA-256 해시 + ValidationGate |

---

## 아키텍처

```
운영자 (브라우저)
      │
      ▼
┌─────────────────┐
│  Next.js 14     │  승인 대시보드 — 에피소드 상태·비용 실시간 표시
└────────┬────────┘
         │ REST API
         ▼
┌─────────────────┐
│  FastAPI        │  ① 사주 계산 (결정론적)  ② Claude 해석  ③ ValidationGate
└────────┬────────┘
         │ Background Task
         ▼
┌─────────────────────────────────────────────┐
│  8단계 파이프라인                             │
│  계산 → 해석 → 씬분할 → TTS → 자막 → 렌더   │
└─────────────────────────────────────────────┘
         │
         ▼
  PostgreSQL + Redis   (에피소드·비용·자산 관리)
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| 프런트엔드 | Next.js 14 (App Router, TypeScript) |
| 백엔드 API | FastAPI + asyncpg |
| 사주 계산 | sxtwl · korean-lunar-calendar |
| AI 해석 | Claude Sonnet (Anthropic API) |
| 음성 합성 | Edge TTS (ko-KR-SunHiNeural) |
| 영상 렌더링 | Remotion |
| 데이터베이스 | PostgreSQL + Prisma ORM |
| 작업 큐 | BullMQ + Redis |
| 패키지 관리 | pnpm workspaces · uv |

---

## 빠른 시작

### 준비물

- Docker Desktop
- Node.js 18+ & pnpm
- Python 3.11+ & uv
- [Anthropic API Key](https://console.anthropic.com)

### 실행

```bash
# 1. 클론
git clone https://github.com/david1005910/SAJU_30days_Linux.git
cd SAJU_30days_Linux

# 2. 환경변수 설정
cp .env.example .env
# ANTHROPIC_API_KEY 입력

# 3. 전체 시스템 시작
./start.sh

# 4. 대시보드 접속
open http://localhost:3000
```

### 30일 전체 자동 생성

```bash
python3 scripts/auto_pipeline.py   # 생성 → 승인 완전 자동화
```

---

## 8단계 파이프라인

```
사주 계산  →  Claude 해석  →  씬 분할  →  이미지 생성
                                              ↓
YouTube ←  렌더링  ←  자막 동기화  ←  Edge TTS
```

각 단계는 PostgreSQL에 상태를 기록하며, 실패 시 자동 재시도합니다.

---

## 30일 커리큘럼

| 주차 | 주제 |
|------|------|
| 1주차 | 사주 기초 — 천간지지, 오행, 일간 |
| 2주차 | 십성 이해 — 비견·식신·재성·관성·인성 |
| 3주차 | 시간과 운 — 대운, 세운, 신살 |
| 4~5주차 | 실전 분석 — 갑목~계수 일간별 심화 |

---

## 실측 비용

Claude Sonnet 기준 30편 실측값:

```
Claude 입력 토큰   $0.077  (29편 기준)
Claude 출력 토큰   $1.309
사주 계산 / TTS    $0.000  (무료)
─────────────────────────
합계               $1.386  → 편당 $0.048
```

---

## 프로젝트 구조

```
.
├── services/api/       # FastAPI — 사주 계산·Claude 해석·파이프라인
│   ├── saju/           # 결정론적 계산 엔진
│   └── interpret/      # Claude 클라이언트 + ValidationGate
├── apps/
│   ├── web/            # Next.js 운영 대시보드
│   └── worker/         # BullMQ 파이프라인 워커
├── packages/
│   ├── db/             # Prisma 스키마 + 마이그레이션
│   └── remotion/       # React 영상 컴포지션
├── curriculum/
│   └── 30day.yaml      # 30일 에피소드 커리큘럼
└── infra/
    └── docker-compose.yml
```

---

## 기여하기

```bash
git checkout -b feature/이름
git commit -m "feat: 설명"
git push origin feature/이름
# Pull Request 생성
```

버그 제보·아이디어는 [Issues](https://github.com/david1005910/SAJU_30days_Linux/issues)로 남겨주세요.

---

## 라이선스

MIT © 2026 david1005910

---

<div align="center">

이 프로젝트가 도움이 됐다면 ⭐ Star를 눌러주세요!

[⭐ Star](https://github.com/david1005910/SAJU_30days_Linux) · [🐛 Issues](https://github.com/david1005910/SAJU_30days_Linux/issues) · **Built with Claude Code**

</div>
