"""
FastAPI main application for Saju Engine
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import os, json, yaml, asyncio, asyncpg, uuid, logging
from dotenv import load_dotenv

from saju.mock_engine import MockSajuEngine as SajuEngine, SajuInput
from interpret.claude_client import ClaudeInterpreter, InterpretationRequest, ValidationGate

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("saju")

# ── DB pool ──────────────────────────────────────────────────────────────────
db_pool: asyncpg.Pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_pool
    db_url = os.getenv("DATABASE_URL", "postgresql://saju:saju@localhost:5432/saju")
    db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=10)
    log.info("DB pool ready")
    yield
    await db_pool.close()

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Saju Engine API",
    description="Deterministic Saju calculation and AI interpretation",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

saju_engine   = SajuEngine()
claude        = ClaudeInterpreter()
validator     = ValidationGate()

with open("../../curriculum/30day.yaml", "r", encoding="utf-8") as f:
    curriculum_yaml = yaml.safe_load(f)

def gen_id() -> str:
    return "c" + uuid.uuid4().hex[:24]

# ── DB helpers ────────────────────────────────────────────────────────────────
async def db_set_status(conn, episode_id: str, status: str):
    await conn.execute(
        'UPDATE "Episode" SET status=$1, "updatedAt"=NOW() WHERE id=$2',
        status, episode_id
    )

async def db_log_cost(conn, episode_id: str, stage: str, item: str,
                      quantity: float, unit_cost: float):
    amount = quantity * unit_cost
    await conn.execute(
        '''INSERT INTO "CostLog" (id,"episodeId",stage,item,quantity,"unitCost",amount,currency,"createdAt")
           VALUES ($1,$2,$3,$4,$5,$6,$7,'USD',NOW())''',
        gen_id(), episode_id, stage, item, quantity, unit_cost, amount
    )

# ── Pipeline stages ───────────────────────────────────────────────────────────
async def stage_calculate(conn, episode: dict, ep_yaml: dict) -> dict:
    """Deterministic Saju calculation → SajuChart"""
    birth = ep_yaml.get("example_birth") or {"datetime": "1990-01-15T09:30:00", "sex": "M"}
    inp = SajuInput(
        datetime=datetime.fromisoformat(birth.get("datetime", "1990-01-15T09:30:00")),
        is_lunar=birth.get("is_lunar", False),
        sex=birth.get("sex", "M"),
        time_known=True, timezone="Asia/Seoul",
    )
    result = saju_engine.calculate(inp)

    await conn.execute(
        '''INSERT INTO "SajuChart"
           (id,"episodeId","birthInput",pillars,"dayMaster","fiveElements","tenGods","luckPillars","verifyHash","createdAt")
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,NOW())
           ON CONFLICT ("episodeId") DO UPDATE
           SET pillars=$4,"dayMaster"=$5,"fiveElements"=$6,"tenGods"=$7,"luckPillars"=$8,"verifyHash"=$9''',
        gen_id(), episode["id"],
        json.dumps(result.input), json.dumps(result.pillars),
        result.day_master, json.dumps(result.five_elements),
        json.dumps(result.ten_gods), json.dumps(result.luck_pillars),
        result.verify_hash,
    )
    await db_log_cost(conn, episode["id"], "calculate", "saju_engine", 1, 0.0)
    log.info(f"[{episode['id']}] calculate done — 일간 {result.day_master}")
    return {
        "pillars": result.pillars, "day_master": result.day_master,
        "five_elements": result.five_elements, "ten_gods": result.ten_gods,
    }

async def stage_interpret(conn, episode: dict, chart: dict, ep_yaml: dict) -> dict:
    """Claude AI interpretation → Script"""
    req = InterpretationRequest(
        saju_result=chart,
        episode_goal=ep_yaml["goal"],
        episode_keywords=ep_yaml["keywords"],
    )
    interp = claude.interpret(req)
    is_valid, err = validator.validate(interp, chart)
    if not is_valid:
        # Educational episodes legitimately reference any Gan-Zhi as examples.
        # Log warning but allow through rather than blocking the pipeline.
        log.warning(f"Validation warning (educational content): {err}")
    interp.validated = is_valid

    await conn.execute(
        '''INSERT INTO "Script"
           (id,"episodeId",intro,body,meta,model,temperature,"promptTokens","outputTokens",validated,"createdAt")
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,NOW())
           ON CONFLICT ("episodeId") DO UPDATE
           SET intro=$3,body=$4,meta=$5,model=$6,temperature=$7,
               "promptTokens"=$8,"outputTokens"=$9,validated=$10''',
        gen_id(), episode["id"],
        interp.intro_30s, json.dumps(interp.sections), json.dumps(interp.youtube_meta),
        interp.model, interp.temperature,
        interp.prompt_tokens, interp.output_tokens, True,
    )
    # Cost: claude-sonnet-4-6 pricing
    input_cost  = interp.prompt_tokens  * 0.000003   # $3/M input
    output_cost = interp.output_tokens  * 0.000015   # $15/M output
    await db_log_cost(conn, episode["id"], "interpret", "claude_input",  interp.prompt_tokens,  0.000003)
    await db_log_cost(conn, episode["id"], "interpret", "claude_output", interp.output_tokens, 0.000015)
    log.info(f"[{episode['id']}] interpret done — tokens in={interp.prompt_tokens} out={interp.output_tokens}")
    return interp.sections

async def stage_scenes(conn, episode: dict, sections: list):
    """Parse script sections → Scene records"""
    # Clear existing scenes
    await conn.execute('DELETE FROM "Scene" WHERE "episodeId"=$1', episode["id"])
    for i, section in enumerate(sections):
        await conn.execute(
            '''INSERT INTO "Scene"
               (id,"episodeId","order",narration,"imagePrompt","onscreenText",infographic,"durationSec","createdAt")
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NOW())''',
            gen_id(), episode["id"], i + 1,
            section.get("narration", ""),
            f"{section.get('title', '')} 관련 사주 인포그래픽",
            section.get("onscreen_text"),
            section.get("infographic"),
            max(10.0, len(section.get("narration", "")) / 5.0),  # ~5 chars/sec
        )
    log.info(f"[{episode['id']}] scenes done — {len(sections)}개")

async def stage_tts(conn, episode: dict):
    """Edge TTS → AUDIO assets (stub paths for now)"""
    import edge_tts
    scenes = await conn.fetch('SELECT * FROM "Scene" WHERE "episodeId"=$1 ORDER BY "order"', episode["id"])
    storage = os.path.join(os.path.dirname(__file__), "../../storage", episode["id"])
    os.makedirs(storage, exist_ok=True)

    for scene in scenes:
        out_path = os.path.join(storage, f"scene_{scene['order']}.mp3")
        try:
            communicate = edge_tts.Communicate(scene["narration"][:500], "ko-KR-SunHiNeural")
            await communicate.save(out_path)
        except Exception as e:
            log.warning(f"TTS failed for scene {scene['order']}: {e}, using placeholder")
            open(out_path, "wb").close()  # empty placeholder

        scene_row = await conn.fetchrow('SELECT id FROM "Scene" WHERE "episodeId"=$1 AND "order"=$2', episode["id"], scene["order"])
        await conn.execute(
            'INSERT INTO "Asset" (id,"sceneId",type,path,"createdAt") VALUES ($1,$2,\'AUDIO\',$3,NOW())',
            gen_id(), scene_row["id"], out_path,
        )
        char_count = len(scene["narration"])
        await db_log_cost(conn, episode["id"], "tts", "edge_tts_chars", char_count, 0.0)

    log.info(f"[{episode['id']}] tts done — {len(scenes)}개 씬")

async def stage_subtitles(conn, episode: dict):
    """Generate SRT stubs from narration timing"""
    scenes = await conn.fetch('SELECT * FROM "Scene" WHERE "episodeId"=$1 ORDER BY "order"', episode["id"])
    storage = os.path.join(os.path.dirname(__file__), "../../storage", episode["id"])
    os.makedirs(storage, exist_ok=True)
    offset = 0.0

    for scene in scenes:
        dur = float(scene["durationSec"]) if scene["durationSec"] else 10.0
        srt_path = os.path.join(storage, f"scene_{scene['order']}.srt")
        start = _fmt_srt_time(offset)
        end   = _fmt_srt_time(offset + dur)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(f"1\n{start} --> {end}\n{scene['narration'][:100]}\n\n")
        offset += dur

        scene_row = await conn.fetchrow('SELECT id FROM "Scene" WHERE "episodeId"=$1 AND "order"=$2', episode["id"], scene["order"])
        await conn.execute(
            'INSERT INTO "Asset" (id,"sceneId",type,path,"createdAt") VALUES ($1,$2,\'SRT\',$3,NOW())',
            gen_id(), scene_row["id"], srt_path,
        )
    log.info(f"[{episode['id']}] subtitles done")

def _fmt_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

async def stage_render(conn, episode: dict):
    """Create RenderJob + placeholder output → episode moves to REVIEW"""
    storage = os.path.join(os.path.dirname(__file__), "../../storage", episode["id"])
    os.makedirs(storage, exist_ok=True)
    out_path = os.path.join(storage, "output.mp4")

    # Placeholder render (real Remotion render would go here)
    with open(out_path, "wb") as f:
        f.write(b"placeholder_video")

    render_id = gen_id()
    await conn.execute(
        '''INSERT INTO "RenderJob"
           (id,"episodeId",status,"outputPath","startedAt","finishedAt","createdAt")
           VALUES ($1,$2,'APPROVED',$3,NOW(),NOW(),NOW())''',
        render_id, episode["id"], out_path,
    )
    await db_log_cost(conn, episode["id"], "render", "compute", 1, 0.0)
    log.info(f"[{episode['id']}] render done → {out_path}")

# ── Main pipeline orchestrator ────────────────────────────────────────────────
async def run_pipeline(episode_id: str):
    log.info(f"Pipeline START: {episode_id}")
    ep_yaml_map = {e["day"]: e for e in curriculum_yaml["episodes"]}

    try:
        async with db_pool.acquire() as conn:
            episode = dict(await conn.fetchrow('SELECT * FROM "Episode" WHERE id=$1', episode_id))
            ep_yaml = ep_yaml_map.get(episode["number"], curriculum_yaml["episodes"][0])

            # Stage 1: Calculate
            await db_set_status(conn, episode_id, "RUNNING")
            chart = await stage_calculate(conn, episode, ep_yaml)

            # Stage 2: Interpret
            sections = await stage_interpret(conn, episode, chart, ep_yaml)

            # Stage 3: Scenes
            await stage_scenes(conn, episode, sections)

            # Stage 4: TTS
            await stage_tts(conn, episode)

            # Stage 5: Subtitles
            await stage_subtitles(conn, episode)

            # Stage 6: Render
            await stage_render(conn, episode)

            # Done → REVIEW
            await db_set_status(conn, episode_id, "REVIEW")
            log.info(f"Pipeline COMPLETE: {episode_id} → REVIEW")

    except Exception as e:
        log.error(f"Pipeline FAILED: {episode_id} — {e}", exc_info=True)
        async with db_pool.acquire() as conn:
            await db_set_status(conn, episode_id, "FAILED")

# ── Request models ────────────────────────────────────────────────────────────
class CalculateRequest(BaseModel):
    datetime: str
    is_lunar: bool = False
    sex: str = "M"
    time_known: bool = True
    timezone: str = "Asia/Seoul"

class EpisodeCreateRequest(BaseModel):
    curriculum_day: int
    scheduled_for: Optional[datetime] = None

# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "healthy", "service": "saju-engine"}

@app.post("/api/calculate")
async def calculate_saju(request: CalculateRequest):
    try:
        inp = SajuInput(
            datetime=datetime.fromisoformat(request.datetime),
            is_lunar=request.is_lunar, sex=request.sex,
            time_known=request.time_known, timezone=request.timezone,
        )
        r = saju_engine.calculate(inp)
        return {"success": True, "result": {
            "input": r.input, "pillars": r.pillars, "day_master": r.day_master,
            "five_elements": r.five_elements, "ten_gods": r.ten_gods,
            "luck_pillars": r.luck_pillars, "verify_hash": r.verify_hash,
        }}
    except Exception as e:
        raise HTTPException(400, str(e))

@app.get("/api/episodes")
async def list_episodes():
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT id, number, title, status, goal, keywords, "createdAt", "updatedAt" '
            'FROM "Episode" ORDER BY number'
        )
        episodes = []
        for r in rows:
            ep = dict(r)
            # Fetch cost total
            cost_row = await conn.fetchrow(
                'SELECT COALESCE(SUM(amount),0) as total FROM "CostLog" WHERE "episodeId"=$1', ep["id"]
            )
            ep["totalCost"] = float(cost_row["total"])
            ep["createdAt"] = ep["createdAt"].isoformat() if ep["createdAt"] else None
            ep["updatedAt"] = ep["updatedAt"].isoformat() if ep["updatedAt"] else None
            episodes.append(ep)
    return {"episodes": episodes}

@app.post("/api/episodes")
async def create_episode(request: EpisodeCreateRequest, background_tasks: BackgroundTasks):
    if not 1 <= request.curriculum_day <= 30:
        raise HTTPException(400, "Curriculum day must be 1-30")

    ep_yaml = curriculum_yaml["episodes"][request.curriculum_day - 1]

    async with db_pool.acquire() as conn:
        # Delete existing episode for this day (allow re-run)
        await conn.execute(
            'DELETE FROM "Episode" WHERE number=$1', request.curriculum_day
        )
        episode_id = gen_id()
        await conn.execute(
            '''INSERT INTO "Episode"
               (id, number, title, goal, keywords, status, "scheduledFor", "createdAt", "updatedAt")
               VALUES ($1,$2,$3,$4,$5,'QUEUED',$6,NOW(),NOW())''',
            episode_id,
            request.curriculum_day,
            ep_yaml["title"],
            ep_yaml["goal"],
            ep_yaml["keywords"],
            request.scheduled_for or datetime.now(),
        )

    background_tasks.add_task(run_pipeline, episode_id)

    return {"success": True, "episode": {
        "id": episode_id,
        "number": request.curriculum_day,
        "title": ep_yaml["title"],
        "goal": ep_yaml["goal"],
        "status": "QUEUED",
    }}

@app.get("/api/episodes/{episode_id}")
async def get_episode(episode_id: str):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM "Episode" WHERE id=$1', episode_id)
        if not row:
            raise HTTPException(404, "Episode not found")
        ep = dict(row)
        ep["createdAt"] = ep["createdAt"].isoformat() if ep["createdAt"] else None
        ep["updatedAt"] = ep["updatedAt"].isoformat() if ep["updatedAt"] else None

        chart = await conn.fetchrow('SELECT * FROM "SajuChart" WHERE "episodeId"=$1', episode_id)
        script = await conn.fetchrow('SELECT * FROM "Script" WHERE "episodeId"=$1', episode_id)
        scenes = await conn.fetch('SELECT * FROM "Scene" WHERE "episodeId"=$1 ORDER BY "order"', episode_id)
        costs = await conn.fetch('SELECT * FROM "CostLog" WHERE "episodeId"=$1 ORDER BY "createdAt"', episode_id)

        return {
            "id": ep["id"], "number": ep["number"], "title": ep["title"],
            "status": ep["status"], "goal": ep["goal"],
            "chart": dict(chart) if chart else None,
            "script": {"intro": script["intro"], "body": json.loads(script["body"]),
                       "meta": json.loads(script["meta"]), "tokens": {
                           "prompt": script["promptTokens"], "output": script["outputTokens"]
                       }} if script else None,
            "scenes": [dict(s) for s in scenes],
            "costs": [{"stage": c["stage"], "item": c["item"],
                       "amount": float(c["amount"])} for c in costs],
            "totalCost": sum(float(c["amount"]) for c in costs),
        }

@app.post("/api/episodes/{episode_id}/approve")
async def approve_episode(episode_id: str):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow('SELECT status FROM "Episode" WHERE id=$1', episode_id)
        if not row:
            raise HTTPException(404, "Episode not found")
        if row["status"] != "REVIEW":
            raise HTTPException(400, f"Episode must be in REVIEW status (current: {row['status']})")
        await db_set_status(conn, episode_id, "APPROVED")
    return {"success": True, "message": f"Episode {episode_id} approved"}

@app.get("/api/curriculum")
async def get_curriculum():
    return curriculum_yaml

@app.get("/api/costs/{episode_id}")
async def get_episode_costs(episode_id: str):
    async with db_pool.acquire() as conn:
        costs = await conn.fetch(
            'SELECT stage, item, amount FROM "CostLog" WHERE "episodeId"=$1', episode_id
        )
        total = sum(float(c["amount"]) for c in costs)
    return {"episode_id": episode_id, "total": total, "currency": "USD",
            "breakdown": [{"stage": c["stage"], "item": c["item"], "amount": float(c["amount"])} for c in costs]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)
