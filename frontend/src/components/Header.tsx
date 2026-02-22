export default function Header({
  balance,
  username,
}: {
  balance: number;
  username?: string;
}) {
  const initial = username ? username[0].toUpperCase() : "?";

  return (
    <header className="border-b-4 border-hex-gold bg-hex-bg-alt">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        {/* Brand */}
        <div className="flex items-baseline gap-3">
          <h1 className="font-serif text-4xl font-black tracking-tight text-hex-gold">
            NASHORDAQ
          </h1>
          <span className="hidden text-xs font-medium uppercase tracking-[0.3em] text-hex-bronze sm:inline">
            Fantasy Market
          </span>
        </div>

        {/* Account bar */}
        <div className="flex items-center gap-6">
          <div className="border-2 border-hex-gold-dim px-4 py-2 shadow-brutal-sm">
            <span className="text-xs uppercase tracking-wider text-hex-bronze">
              Balance
            </span>
            <p className="font-mono text-lg font-bold text-hex-gold">
              {balance.toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
              <span className="ml-1 text-xs text-hex-bronze">G</span>
            </p>
          </div>
          <div className="h-10 w-10 border-2 border-hex-gold bg-hex-panel text-center font-serif text-lg leading-9 font-bold text-hex-gold">
            {initial}
          </div>
        </div>
      </div>
    </header>
  );
}
