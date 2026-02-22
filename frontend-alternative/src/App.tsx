import {
  mockLeaderboard,
  mockOrders,
  mockPlayers,
  mockPortfolio,
  mockTransactions,
  mockUser,
} from "./mockData";

function App() {
  const pendingOrders = mockOrders.filter(
    (order) => order.status === "PENDING",
  );

  return (
    <div className="min-h-screen bg-hex-bg p-4 text-hex-gold sm:p-8">
      <main className="mx-auto grid w-full max-w-7xl grid-cols-1 border-4 border-hex-gold bg-hex-bg shadow-brutal xl:grid-cols-[1.45fr_1fr]">
        <section className="border-b-4 border-hex-gold p-6 xl:border-b-0 xl:border-r-4 xl:p-10">
          <p className="font-mono text-xs uppercase tracking-[0.3em] text-hex-bronze">
            static/mockData.ts
          </p>
          <h1 className="mt-3 font-sans text-4xl font-extrabold uppercase tracking-[0.08em] sm:text-5xl">
            Nashordaq Exchange
          </h1>
          <p className="mt-4 max-w-xl font-mono text-sm leading-relaxed text-hex-bronze">
            Final mock interface: all core product features are represented with
            static data and disabled trading actions.
          </p>
        </section>

        <aside className="grid grid-cols-2 border-b-4 border-hex-gold font-mono xl:border-b-0 xl:grid-cols-1">
          <div className="border-r-4 border-hex-gold p-4 xl:border-r-0 xl:border-b-4">
            <p className="text-xs uppercase tracking-[0.2em] text-hex-bronze">
              Connection
            </p>
            <p className="mt-2 text-lg font-bold text-hex-magic">
              Offline Mock
            </p>
          </div>
          <div className="p-4 xl:border-b-4 xl:border-hex-gold">
            <p className="text-xs uppercase tracking-[0.2em] text-hex-bronze">
              User
            </p>
            <p className="mt-2 text-lg font-bold">{mockUser.username}</p>
          </div>
          <div className="col-span-2 border-t-4 border-hex-gold p-4 xl:border-t-0">
            <p className="text-xs uppercase tracking-[0.2em] text-hex-bronze">
              Portfolio Total
            </p>
            <p className="mt-2 text-xl font-bold">
              ${mockPortfolio.total_value.toFixed(2)}
            </p>
            <ul className="mt-3 space-y-1 text-xs text-hex-bronze">
              {mockPortfolio.holdings.map((holding) => (
                <li
                  key={holding.player_id}
                  className="flex items-center justify-between"
                >
                  <span>{holding.player_name}</span>
                  <span>{holding.quantity} sh</span>
                </li>
              ))}
            </ul>
          </div>
        </aside>

        <section className="col-span-full border-b-4 border-hex-gold overflow-x-auto">
          <table className="w-full border-collapse font-mono text-sm">
            <thead>
              <tr className="border-b-4 border-hex-gold bg-hex-gold text-hex-bg">
                <th className="border-r-2 border-hex-bg px-4 py-3 text-left uppercase tracking-[0.16em]">
                  Player
                </th>
                <th className="border-r-2 border-hex-bg px-4 py-3 text-left uppercase tracking-[0.16em]">
                  Riot ID
                </th>
                <th className="border-r-2 border-hex-bg px-4 py-3 text-right uppercase tracking-[0.16em]">
                  Current Price
                </th>
                <th className="px-4 py-3 text-right uppercase tracking-[0.16em]">
                  24h Signal
                </th>
              </tr>
            </thead>
            <tbody>
              {mockPlayers.map((player) => {
                const signal = `${player.lp_signal_24h >= 0 ? "+" : ""}${player.lp_signal_24h} LP`;
                const signalColor =
                  player.lp_signal_24h >= 0
                    ? "text-hex-magic"
                    : "text-hex-zaun";

                return (
                  <tr key={player.id} className="border-b-2 border-hex-gold/50">
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3">
                      <p className="font-sans text-xl font-bold uppercase">
                        {player.display_name}
                      </p>
                    </td>
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3 text-hex-bronze">
                      {player.game_name}#{player.tag_line}
                    </td>
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3 text-right text-base font-semibold">
                      ${player.current_price.toFixed(2)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right text-xs font-bold uppercase tracking-[0.16em] ${signalColor}`}
                    >
                      {signal}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <section className="border-b-4 border-hex-gold p-5 xl:border-b-0 xl:border-r-4">
          <div className="flex items-end justify-between gap-3 border-b-2 border-hex-gold/50 pb-3">
            <h2 className="font-sans text-2xl font-black uppercase tracking-[0.08em]">
              Trading
            </h2>
            <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-hex-zaun">
              Placement Disabled
            </span>
          </div>
          <form className="mt-4 grid grid-cols-1 gap-3 font-mono text-sm sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs uppercase tracking-[0.16em] text-hex-bronze">
                Player
              </span>
              <select
                disabled
                className="w-full border-2 border-hex-gold bg-hex-bg px-3 py-2 text-hex-bronze disabled:cursor-not-allowed"
              >
                {mockPlayers.map((player) => (
                  <option key={player.id}>{player.display_name}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-xs uppercase tracking-[0.16em] text-hex-bronze">
                Side
              </span>
              <select
                disabled
                className="w-full border-2 border-hex-gold bg-hex-bg px-3 py-2 text-hex-bronze disabled:cursor-not-allowed"
              >
                <option>BUY</option>
                <option>SELL</option>
              </select>
            </label>
            <label className="block sm:col-span-2">
              <span className="mb-1 block text-xs uppercase tracking-[0.16em] text-hex-bronze">
                Quantity (whole shares)
              </span>
              <input
                disabled
                type="number"
                min={1}
                value={3}
                readOnly
                className="w-full border-2 border-hex-gold bg-hex-bg px-3 py-2 text-hex-bronze disabled:cursor-not-allowed"
              />
            </label>
            <button
              type="button"
              disabled
              className="sm:col-span-2 border-4 border-hex-gold bg-hex-gold px-3 py-3 text-xs font-bold uppercase tracking-[0.2em] text-hex-bg disabled:cursor-not-allowed disabled:bg-hex-bronze"
            >
              Place Order (Mock Locked)
            </button>
          </form>
          <p className="mt-3 font-mono text-xs uppercase tracking-[0.14em] text-hex-bronze">
            Pending orders shown below can be reviewed, but cancel action is
            also disabled.
          </p>
          <ul className="mt-4 space-y-2 font-mono text-xs">
            {pendingOrders.map((order) => (
              <li
                key={order.id}
                className="grid grid-cols-[1fr_auto] items-center gap-3 border-2 border-hex-gold/60 px-3 py-2"
              >
                <span>
                  #{order.id} {order.side} {order.quantity} {order.player_name}
                </span>
                <button
                  type="button"
                  disabled
                  className="border-2 border-hex-zaun px-2 py-1 text-[10px] font-bold uppercase tracking-[0.15em] text-hex-zaun disabled:opacity-60"
                >
                  Cancel Disabled
                </button>
              </li>
            ))}
          </ul>
        </section>

        <section className="border-b-4 border-hex-gold p-5 xl:border-b-0">
          <h2 className="border-b-2 border-hex-gold/50 pb-3 font-sans text-2xl font-black uppercase tracking-[0.08em]">
            Leaderboard
          </h2>
          <ol className="mt-4 space-y-2 font-mono text-sm">
            {mockLeaderboard.map((entry) => (
              <li
                key={entry.username}
                className="grid grid-cols-[auto_1fr_auto] items-center gap-3 border-2 border-hex-gold/60 px-3 py-2"
              >
                <span className="text-hex-bronze">#{entry.rank}</span>
                <span className="truncate font-semibold text-hex-gold">
                  {entry.username}
                </span>
                <span className="text-hex-magic">
                  ${entry.total_value.toFixed(2)}
                </span>
              </li>
            ))}
          </ol>
          <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-2 border-t-2 border-hex-gold/50 pt-4 font-mono text-xs text-hex-bronze">
            <dt>Account Created</dt>
            <dd className="text-right text-hex-gold">
              {new Date(mockUser.created_at).toLocaleDateString()}
            </dd>
            <dt>Cash Balance</dt>
            <dd className="text-right text-hex-gold">
              ${mockUser.balance.toFixed(2)}
            </dd>
            <dt>Holdings Count</dt>
            <dd className="text-right text-hex-gold">
              {mockPortfolio.holdings.length}
            </dd>
          </dl>
        </section>

        <section className="col-span-full border-t-4 border-hex-gold p-0">
          <div className="border-b-2 border-hex-gold/50 px-4 py-3 font-mono text-xs uppercase tracking-[0.2em] text-hex-bronze">
            Orders
          </div>
          <table className="w-full border-collapse font-mono text-xs sm:text-sm">
            <thead>
              <tr className="border-b-2 border-hex-gold/70">
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-left uppercase tracking-[0.16em]">
                  ID
                </th>
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-left uppercase tracking-[0.16em]">
                  Player
                </th>
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-left uppercase tracking-[0.16em]">
                  Side
                </th>
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-right uppercase tracking-[0.16em]">
                  Qty
                </th>
                <th className="px-4 py-3 text-right uppercase tracking-[0.16em]">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {mockOrders.map((order) => {
                const sideColor =
                  order.side === "BUY" ? "text-hex-magic" : "text-hex-zaun";
                const statusColor =
                  order.status === "FILLED"
                    ? "text-hex-magic"
                    : order.status === "PENDING"
                      ? "text-hex-gold"
                      : "text-hex-bronze";

                return (
                  <tr key={order.id} className="border-b-2 border-hex-gold/40">
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3">
                      #{order.id}
                    </td>
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3">
                      {order.player_name}
                    </td>
                    <td
                      className={`border-r-2 border-hex-gold/60 px-4 py-3 font-bold uppercase ${sideColor}`}
                    >
                      {order.side}
                    </td>
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3 text-right">
                      {order.quantity}
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-bold uppercase ${statusColor}`}
                    >
                      {order.status}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>

        <section className="col-span-full border-t-4 border-hex-gold p-0">
          <div className="border-b-2 border-hex-gold/50 px-4 py-3 font-mono text-xs uppercase tracking-[0.2em] text-hex-bronze">
            Transaction History
          </div>
          <table className="w-full border-collapse font-mono text-xs sm:text-sm">
            <thead>
              <tr className="border-b-2 border-hex-gold/70">
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-left uppercase tracking-[0.16em]">
                  ID
                </th>
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-left uppercase tracking-[0.16em]">
                  Player
                </th>
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-left uppercase tracking-[0.16em]">
                  Side
                </th>
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-right uppercase tracking-[0.16em]">
                  Qty
                </th>
                <th className="border-r-2 border-hex-gold/60 px-4 py-3 text-right uppercase tracking-[0.16em]">
                  Exec
                </th>
                <th className="px-4 py-3 text-right uppercase tracking-[0.16em]">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {mockTransactions.map((transaction) => {
                const sideColor =
                  transaction.side === "BUY"
                    ? "text-hex-magic"
                    : "text-hex-zaun";
                const statusColor =
                  transaction.status === "FILLED"
                    ? "text-hex-magic"
                    : transaction.status === "PENDING"
                      ? "text-hex-gold"
                      : "text-hex-bronze";

                return (
                  <tr
                    key={transaction.id}
                    className="border-b-2 border-hex-gold/40"
                  >
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3">
                      #{transaction.id}
                    </td>
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3">
                      {transaction.player_name}
                    </td>
                    <td
                      className={`border-r-2 border-hex-gold/60 px-4 py-3 font-bold uppercase ${sideColor}`}
                    >
                      {transaction.side}
                    </td>
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3 text-right">
                      {transaction.quantity}
                    </td>
                    <td className="border-r-2 border-hex-gold/60 px-4 py-3 text-right">
                      {transaction.execution_price === null
                        ? "--"
                        : `$${transaction.execution_price.toFixed(2)}`}
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-bold uppercase ${statusColor}`}
                    >
                      {transaction.status}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      </main>
    </div>
  );
}

export default App;
