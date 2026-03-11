import { useEffect, useRef, useState } from "react";
import { ApiError, useClaimPoro, usePoroState } from "../api";

const PORO_SIZE_PX = 80;
const REWARD_BURST_MS = 1600;

const PORO_ASSETS: Record<string, string> = {
  "tier-1": "/poro/tier-1.png",
  "tier-2": "/poro/tier-2.png",
  "tier-3": "/poro/tier-3.png",
  "tier-4": "/poro/tier-4.png",
  "tier-5": "/poro/tier-5.png",
  "tier-6": "/poro/tier-6.png",
};

const PORO_ANIMATED_ASSETS: Record<string, [string, string]> = {
  "tier-1": ["/poro/tier-1.png", "/poro/tier-1_run.png"],
  "tier-2": ["/poro/tier-2.png", "/poro/tier-2_run.png"],
  "tier-3": ["/poro/tier-3.png", "/poro/tier-3_run.png"],
  "tier-4": ["/poro/tier-4.png", "/poro/tier-4_run.png"],
  "tier-5": ["/poro/tier-5.png", "/poro/tier-5_run.png"],
  "tier-6": ["/poro/tier-6.png", "/poro/tier-6_run.png"],
};

const RUN_FRAME_INTERVAL_MS = 140;

interface ViewportSize {
  width: number;
  height: number;
}

interface ScreenPoint {
  x: number;
  y: number;
}

interface RewardBurst {
  id: string;
  text: string;
  x: number;
  y: number;
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function lerp(start: number, end: number, progress: number) {
  return start + (end - start) * progress;
}

function toScreenPoint(
  x: number,
  y: number,
  viewport: ViewportSize,
): ScreenPoint {
  return {
    x: viewport.width * x - PORO_SIZE_PX / 2,
    y: viewport.height * y - PORO_SIZE_PX / 2,
  };
}

export default function FlyingPoro({ enabled }: { enabled: boolean }) {
  const { data } = usePoroState(enabled);
  const claimPoro = useClaimPoro();
  const [viewport, setViewport] = useState<ViewportSize>({
    width: window.innerWidth,
    height: window.innerHeight,
  });
  const [dismissedSpawnId, setDismissedSpawnId] = useState<string | null>(null);
  const [rewardBurst, setRewardBurst] = useState<RewardBurst | null>(null);
  const [animationFrame, setAnimationFrame] = useState(0);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const clearTimerRef = useRef<number | null>(null);
  const burstTimerRef = useRef<number | null>(null);
  const animationTimerRef = useRef<number | null>(null);
  const serverOffsetRef = useRef(0);

  const activeSpawn = data?.active_spawn ?? null;
  const visibleSpawn =
    activeSpawn && activeSpawn.spawn_id !== dismissedSpawnId
      ? activeSpawn
      : null;
  const shouldMirrorHorizontally =
    visibleSpawn !== null && visibleSpawn.end_x > visibleSpawn.start_x;

  useEffect(() => {
    serverOffsetRef.current = data
      ? new Date(data.server_time).getTime() - Date.now()
      : 0;
  }, [data]);

  useEffect(() => {
    function handleResize() {
      setViewport({ width: window.innerWidth, height: window.innerHeight });
    }

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (clearTimerRef.current !== null) {
      window.clearTimeout(clearTimerRef.current);
      clearTimerRef.current = null;
    }

    const button = buttonRef.current;
    if (!visibleSpawn || !button) {
      return;
    }

    const now = Date.now() + serverOffsetRef.current;
    const startedAt = new Date(visibleSpawn.spawned_at).getTime();
    const expiresAt = new Date(visibleSpawn.expires_at).getTime();
    const totalDuration = Math.max(1, expiresAt - startedAt);
    const progress = clamp((now - startedAt) / totalDuration, 0, 1);
    const currentPoint = toScreenPoint(
      lerp(visibleSpawn.start_x, visibleSpawn.end_x, progress),
      lerp(visibleSpawn.start_y, visibleSpawn.end_y, progress),
      viewport,
    );
    const endPoint = toScreenPoint(
      visibleSpawn.end_x,
      visibleSpawn.end_y,
      viewport,
    );
    const remainingMs = Math.max(0, expiresAt - now);

    button.style.transitionProperty = "none";
    button.style.transitionDuration = "0ms";
    button.style.transitionTimingFunction = "linear";
    button.style.transform = `translate3d(${currentPoint.x}px, ${currentPoint.y}px, 0)`;

    if (remainingMs === 0) {
      clearTimerRef.current = window.setTimeout(() => {
        setDismissedSpawnId(visibleSpawn.spawn_id);
        clearTimerRef.current = null;
      }, 0);
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      button.style.transitionProperty = "transform";
      button.style.transitionDuration = `${remainingMs}ms`;
      button.style.transitionTimingFunction = "linear";
      button.style.transform = `translate3d(${endPoint.x}px, ${endPoint.y}px, 0)`;
    });

    clearTimerRef.current = window.setTimeout(() => {
      setDismissedSpawnId(visibleSpawn.spawn_id);
      clearTimerRef.current = null;
    }, remainingMs + 100);

    return () => {
      window.cancelAnimationFrame(frame);
      if (clearTimerRef.current !== null) {
        window.clearTimeout(clearTimerRef.current);
        clearTimerRef.current = null;
      }
    };
  }, [viewport, visibleSpawn]);

  useEffect(() => {
    return () => {
      if (burstTimerRef.current !== null) {
        window.clearTimeout(burstTimerRef.current);
      }
      if (animationTimerRef.current !== null) {
        window.clearInterval(animationTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (animationTimerRef.current !== null) {
      window.clearInterval(animationTimerRef.current);
      animationTimerRef.current = null;
    }

    if (!visibleSpawn) {
      return;
    }

    const animationFrames = PORO_ANIMATED_ASSETS[visibleSpawn.asset_key];
    if (!animationFrames) {
      return;
    }

    animationTimerRef.current = window.setInterval(() => {
      setAnimationFrame((current) => (current + 1) % animationFrames.length);
    }, RUN_FRAME_INTERVAL_MS);

    return () => {
      if (animationTimerRef.current !== null) {
        window.clearInterval(animationTimerRef.current);
        animationTimerRef.current = null;
      }
    };
  }, [visibleSpawn]);

  if (!enabled || !data?.enabled || !visibleSpawn) {
    return rewardBurst ? (
      <div
        className="poro-reward-burst"
        style={{
          left: `${rewardBurst.x}px`,
          top: `${rewardBurst.y}px`,
        }}
      >
        {rewardBurst.text}
      </div>
    ) : null;
  }

  const animationFrames = PORO_ANIMATED_ASSETS[visibleSpawn.asset_key];
  const assetSrc = animationFrames
    ? animationFrames[animationFrame]
    : (PORO_ASSETS[visibleSpawn.asset_key] ?? PORO_ASSETS["tier-1"]);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        className="poro-flight"
        onClick={(event) => {
          if (claimPoro.isPending) {
            return;
          }

          const rect = event.currentTarget.getBoundingClientRect();

          claimPoro.mutate(
            { spawn_id: visibleSpawn.spawn_id },
            {
              onSuccess: (result) => {
                setDismissedSpawnId(visibleSpawn.spawn_id);
                setRewardBurst({
                  id: result.spawn_id,
                  text: `+${result.reward_amount.toFixed(0)}`,
                  x: rect.left + PORO_SIZE_PX * 0.25,
                  y: rect.top - 8,
                });
                if (burstTimerRef.current !== null) {
                  window.clearTimeout(burstTimerRef.current);
                }
                burstTimerRef.current = window.setTimeout(() => {
                  setRewardBurst((current) =>
                    current?.id === result.spawn_id ? null : current,
                  );
                  burstTimerRef.current = null;
                }, REWARD_BURST_MS);
              },
              onError: (error) => {
                if (error instanceof ApiError && error.status === 409) {
                  setDismissedSpawnId(visibleSpawn.spawn_id);
                }
              },
            },
          );
        }}
        style={{ width: `${PORO_SIZE_PX}px`, height: `${PORO_SIZE_PX}px` }}
        aria-label={`Claim ${visibleSpawn.reward_amount.toFixed(0)} poros from tier ${visibleSpawn.tier} poro`}
      >
        <img
          src={assetSrc}
          alt=""
          className="poro-flight__image"
          style={{ transform: shouldMirrorHorizontally ? "scaleX(-1)" : undefined }}
          draggable={false}
        />
      </button>

      {rewardBurst && (
        <div
          className="poro-reward-burst"
          style={{
            left: `${rewardBurst.x}px`,
            top: `${rewardBurst.y}px`,
          }}
        >
          {rewardBurst.text}
        </div>
      )}
    </>
  );
}
