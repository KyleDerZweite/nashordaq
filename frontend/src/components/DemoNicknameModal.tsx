import { useState } from "react";
import { useSetDemoNickname } from "../api";

export default function DemoNicknameModal() {
  const [nickname, setNickname] = useState("");
  const setDemoNickname = useSetDemoNickname();

  const trimmed = nickname.trim();
  const isValid = trimmed.length >= 1 && trimmed.length <= 32;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (!isValid) {
      return;
    }

    setDemoNickname.mutate({ display_name: trimmed });
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-hex-bg/80">
      <section className="w-full max-w-md border-4 border-hex-gold bg-hex-panel shadow-brutal-lg">
        <div className="border-b-4 border-hex-gold px-5 py-3">
          <h2 className="font-serif text-xl font-bold text-hex-gold">
            Choose a Nickname
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-4">
          <p className="font-mono text-sm leading-6 text-hex-bronze">
            Pick a display name for the demo session. This is how other
            participants will see you on the leaderboard.
          </p>

          <div>
            <label className="mb-1 block font-mono text-xs uppercase tracking-wider text-hex-bronze">
              Nickname
            </label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              maxLength={32}
              autoFocus
              className="w-full border-2 border-hex-border bg-hex-bg px-3 py-2 font-mono text-sm text-hex-white outline-none focus:border-hex-gold"
              placeholder="1-32 characters"
            />
          </div>

          {setDemoNickname.isError && (
            <p className="font-mono text-xs text-hex-zaun">
              {setDemoNickname.error.message}
            </p>
          )}

          <button
            type="submit"
            disabled={!isValid || setDemoNickname.isPending}
            className={`w-full border-2 py-2.5 font-mono text-sm font-bold uppercase tracking-wider transition-colors ${
              isValid && !setDemoNickname.isPending
                ? "border-hex-gold bg-transparent text-hex-gold hover:bg-hex-gold hover:text-hex-bg"
                : "cursor-not-allowed border-hex-border text-hex-border"
            }`}
          >
            {setDemoNickname.isPending ? "Saving..." : "Start Trading"}
          </button>
        </form>
      </section>
    </div>
  );
}
