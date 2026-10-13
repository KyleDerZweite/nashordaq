import { useGameActivity } from "../api";
import { useIdentityPresentation } from "../contexts/useIdentityPresentation";
import { formatLocalDateTime } from "../utils/format";

export default function GameActivity() {
  const { userName } = useIdentityPresentation();
  const { data, isPending, isError, refetch, isFetching } = useGameActivity();
  return (
    <section
      aria-labelledby="game-activity-heading"
      className="border-2 border-hex-border bg-hex-panel p-4 sm:p-6"
    >
      <h2
        id="game-activity-heading"
        className="font-serif text-2xl text-hex-gold"
      >
        Game activity
      </h2>
      <p className="mt-2 font-mono text-sm text-hex-bronze">
        Administrator interventions in the game are visible to every member.
      </p>
      {isPending && (
        <p role="status" className="mt-4 font-mono text-sm text-hex-bronze">
          Loading game activity...
        </p>
      )}
      {isError && (
        <div role="alert" className="mt-4 font-mono text-sm text-red-300">
          <p>Game activity could not be loaded.</p>
          <button
            type="button"
            disabled={isFetching}
            onClick={() => void refetch()}
            className="mt-2 border border-hex-gold px-3 py-2 text-hex-gold disabled:opacity-50"
          >
            {isFetching ? "Retrying..." : "Retry game activity"}
          </button>
        </div>
      )}
      {data?.length === 0 && (
        <p className="mt-4 font-mono text-sm text-hex-bronze">
          No administrator game interventions yet.
        </p>
      )}
      {data && data.length > 0 && (
        <ol className="mt-4 space-y-4">
          {data.map((event) => (
            <li
              key={event.id}
              className="break-words border border-hex-border bg-hex-bg-alt p-3 font-mono text-sm text-hex-white"
            >
              <p>
                {userName(event.actor.user_id)} restored rescue-loan access for{" "}
                {userName(event.affected.user_id)}.
              </p>
              <p className="mt-2 text-hex-bronze">
                Rescue uses: {event.previous_uses} to {event.new_uses}.
              </p>
              <time
                dateTime={event.created_at}
                className="mt-2 block text-xs text-hex-bronze"
              >
                {formatLocalDateTime(event.created_at)}
              </time>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
