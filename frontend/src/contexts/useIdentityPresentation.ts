import { useMemo } from "react";
import { useIdentities } from "../api/hooks";
import { identityPresentation } from "../utils/identityPresentation";
import { useStreamerMode } from "./useStreamerMode";

export function useIdentityPresentation() {
  const mode = useStreamerMode();
  const { data } = useIdentities();
  const names = useMemo(
    () => identityPresentation(data, mode.isStreamerMode),
    [data, mode.isStreamerMode],
  );
  return { ...mode, ...names };
}
