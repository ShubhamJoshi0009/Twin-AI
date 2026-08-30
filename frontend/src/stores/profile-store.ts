"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

/**
 * Profile store — the single source of truth for everything the AI assistant
 * (and the onboarding wizard) learns about the user and their company.
 *
 * - `business` — the company profile collected conversationally (name,
 *   industry, size, revenue, challenges, goals, priorities).
 * - `personal` — the user's own profile (name, role, email, decision style,
 *   focus areas). Drives greetings, the topbar user menu and settings.
 * - `status` — whether the setup conversation has been completed.
 *
 * Persisted under `bta-profile` so the whole workspace adapts to the user
 * across sessions, even when the backend is offline.
 */

export interface BusinessProfile {
  name: string;
  industry: string;
  industryLabel: string;
  employees: number;
  revenue: number;
  description: string;
  challenges: string[];
  goals: string[];
  priorities: string[];
}

export interface PersonalProfile {
  name: string;
  role: string;
  email: string;
  decisionStyle: string;
  focusAreas: string[];
}

export type ProfileStatus = "idle" | "collecting" | "complete";

interface ProfileState {
  status: ProfileStatus;
  business: BusinessProfile;
  personal: PersonalProfile;
  setStatus: (status: ProfileStatus) => void;
  updateBusiness: (patch: Partial<BusinessProfile>) => void;
  updatePersonal: (patch: Partial<PersonalProfile>) => void;
  /** Merge partials into both profiles (used by the onboarding wizard). */
  replaceProfile: (business: Partial<BusinessProfile>, personal?: Partial<PersonalProfile>) => void;
  resetProfile: () => void;
}

export const DEFAULT_BUSINESS: BusinessProfile = {
  name: "",
  industry: "",
  industryLabel: "",
  employees: 0,
  revenue: 0,
  description: "",
  challenges: [],
  goals: [],
  priorities: [],
};

export const DEFAULT_PERSONAL: PersonalProfile = {
  name: "",
  role: "",
  email: "",
  decisionStyle: "",
  focusAreas: [],
};

export const useProfileStore = create<ProfileState>()(
  persist(
    (set) => ({
      status: "idle",
      business: DEFAULT_BUSINESS,
      personal: DEFAULT_PERSONAL,
      setStatus: (status) => set({ status }),
      updateBusiness: (patch) => set((s) => ({ business: { ...s.business, ...patch } })),
      updatePersonal: (patch) => set((s) => ({ personal: { ...s.personal, ...patch } })),
      replaceProfile: (business, personal) =>
        set((s) => ({
          business: { ...s.business, ...business },
          personal: { ...s.personal, ...(personal ?? {}) },
        })),
      resetProfile: () => set({ status: "idle", business: DEFAULT_BUSINESS, personal: DEFAULT_PERSONAL }),
    }),
    { name: "bta-profile" }
  )
);

/** True when the first-time setup banner should be shown. */
export const needsProfileSetup = (s: Pick<ProfileState, "status" | "business">) =>
  s.status !== "complete" || !(s.business?.name ?? "").trim();
