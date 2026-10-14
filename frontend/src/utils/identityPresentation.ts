import type { IdentityDirectory } from "../types";

function normalName(
  username: string | null,
  gameName: string | null,
  tagLine: string | null,
) {
  const riotName = gameName && tagLine ? `${gameName}#${tagLine}` : null;
  return username && riotName
    ? `${username} (${riotName})`
    : (username ?? riotName ?? "Summoner");
}

// A directory miss never falls back to raw identity data from another response.
export function identityPresentation(
  data: IdentityDirectory | undefined,
  isStreamerMode: boolean,
) {
  const users = new Map(
    data?.users.map((user) => [
      user.user_id,
      isStreamerMode
        ? user.streamer_alias
        : normalName(user.username, user.game_name, user.tag_line),
    ]),
  );
  const players = new Map(
    data?.players.map((player) => [
      player.player_id,
      isStreamerMode
        ? player.streamer_alias
        : normalName(player.username, player.game_name, player.tag_line),
    ]),
  );
  return {
    userName: (id: number | null | undefined) =>
      users.get(id ?? -1) || "Summoner",
    playerName: (id: number | null | undefined) =>
      players.get(id ?? -1) || "Summoner",
  };
}
