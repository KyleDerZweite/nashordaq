import assert from "node:assert/strict";
import test from "node:test";
import { identityPresentation } from "../src/utils/identityPresentation.ts";

const directory = {
  users: [
    {
      user_id: 1,
      username: "RecognizableUser",
      linked_player_id: 11,
      game_name: "RealSummoner",
      tag_line: "PRIVATE",
      streamer_alias: "Ahri",
    },
    {
      user_id: 2,
      username: "UnlinkedUsername",
      linked_player_id: null,
      game_name: null,
      tag_line: null,
      streamer_alias: "Lux",
    },
  ],
  players: [
    {
      player_id: 11,
      username: "RecognizableUser",
      game_name: "RealSummoner",
      tag_line: "PRIVATE",
      streamer_alias: "Ahri",
    },
    {
      player_id: 12,
      username: null,
      game_name: "TrackedSummoner",
      tag_line: "SECRET",
      streamer_alias: "Infinity Edge",
    },
  ],
};

test("normal identities include username and Riot name, with unlinked fallbacks", () => {
  const names = identityPresentation(directory, false);
  assert.equal(names.userName(1), "RecognizableUser (RealSummoner#PRIVATE)");
  assert.equal(names.userName(2), "UnlinkedUsername");
  assert.equal(names.playerName(11), names.userName(1));
  assert.equal(names.playerName(12), "TrackedSummoner#SECRET");
});

test("streamer identities use only persisted aliases for linked and unlinked entities", () => {
  const names = identityPresentation(directory, true);
  assert.equal(names.userName(1), "Ahri");
  assert.equal(names.playerName(11), names.userName(1));
  assert.equal(names.userName(2), "Lux");
  assert.equal(names.playerName(12), "Infinity Edge");
});

test("missing, loading and failed directory lookups expose only a safe placeholder", () => {
  for (const data of [undefined, directory]) {
    for (const mode of [false, true]) {
      const names = identityPresentation(data, mode);
      for (const id of [null, undefined, 999]) {
        assert.equal(names.userName(id), "Summoner");
        assert.equal(names.playerName(id), "Summoner");
      }
    }
  }
  assert.equal(identityPresentation(undefined, true).userName(1), "Summoner");
  assert.equal(
    identityPresentation(undefined, true).playerName(11),
    "Summoner",
  );
});
