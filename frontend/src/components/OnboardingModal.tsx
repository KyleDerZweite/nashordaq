import { useCompleteOnboarding } from "../api";
import PlayerProfileModal from "./PlayerProfileModal";

export default function OnboardingModal() {
  const completeOnboarding = useCompleteOnboarding();

  return (
    <PlayerProfileModal
      title="Complete Your Player Setup"
      description="Enter your Riot account once to join the market."
      submitLabel="Join Market"
      isPending={completeOnboarding.isPending}
      errorMessage={
        completeOnboarding.isError
          ? completeOnboarding.error.message
          : undefined
      }
      onSubmit={(body) => completeOnboarding.mutate(body)}
    />
  );
}
