import { OnboardingWizard } from "@/components/onboarding/onboarding-wizard";

/**
 * Landing / onboarding page — collects the company profile used to build the
 * digital twin. Replaces the old dashboard redirect so first-time users set up
 * their business before entering the app.
 */
export default function Home() {
  return <OnboardingWizard />;
}
