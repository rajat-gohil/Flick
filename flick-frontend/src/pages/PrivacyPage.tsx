import React from "react";
import { useNavigate } from "react-router-dom";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

export default function PrivacyPage() {
  const navigate = useNavigate();

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col antialiased">

      {/* Header */}
      <CinemaHeader
        current="profile"
        title="Privacy Policy"
        subtitle="Data Stewardship"
        onBack={() => {
          if (window.history.length > 1) navigate(-1);
          else navigate("/profile");
        }}
      />

      <div className="w-full max-w-2xl mx-auto flex-1 flex flex-col px-4 sm:px-6 py-6 pb-24 md:pb-12">
        <main className="flex-1 overflow-y-auto">

          <div className="flex items-center gap-3.5 mb-6 pb-4 border-b border-border/60">
            <div className="size-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-[22px]">shield</span>
            </div>
            <div>
              <h2 className="font-editorial text-xl font-bold">Data Stewardship Policy</h2>
              <p className="text-[11px] text-foreground-secondary">Last updated: March 2026</p>
            </div>
          </div>

          {/* TL;DR box */}
          <div className="mb-6 p-4 rounded-xl bg-surface border border-primary/20 shadow-xs">
            <p className="text-[10px] font-semibold text-primary uppercase tracking-widest mb-1">Principles</p>
            <p className="text-xs text-foreground leading-relaxed">
              We retain strictly the data required to facilitate film matching. We do not monetize your data, run commercial ad networks, or track browsing activity outside Flick.
            </p>
          </div>

          <div className="flex flex-col gap-6 text-xs text-foreground-secondary leading-relaxed">

            <Section title="1. Information Collected">
              <p className="mb-2">We process the following data attributes:</p>
              <div className="flex flex-col gap-2">
                <DataItem icon="person" label="Member Credentials" desc="Email address, handle, and securely hashed passwords." />
                <DataItem icon="movie" label="Screening Decisions" desc="Title selections, session codes, and agreed match records." />
                <DataItem icon="devices" label="Telemetry" desc="Browser client attributes strictly for application diagnosis and error triage." />
              </div>
            </Section>

            <Section title="2. Purpose of Processing">
              <ul className="list-disc pl-5 flex flex-col gap-1 text-foreground-secondary">
                <li>Facilitate real-time screening alignment between co-viewers</li>
                <li>Deliver recommendation scoring attuned to user preferences</li>
                <li>Dispatch transactional notices and optional web alerts</li>
              </ul>
            </Section>

            <Section title="3. Third-Party Integrations">
              <p>Flick interfaces with:</p>
              <ul className="list-disc pl-5 mt-1 flex flex-col gap-1 text-foreground-secondary">
                <li><strong className="text-foreground">TMDB</strong> — Film metadata and imagery</li>
                <li><strong className="text-foreground">Email Dispatchers</strong> — Transactional verification delivery</li>
              </ul>
            </Section>

            <Section title="4. Member Rights & Data Deletion">
              You maintain full sovereignty over your data. You may request record extracts or permanently delete your account and all associated logs directly via Member Profile &gt; Account Security &gt; Terminate Account.
            </Section>

            <Section title="5. Contact & Privacy Office">
              For privacy inquiries, data stewardship questions, or data rights requests, write to{" "}
              <a href="mailto:discoverflick@gmail.com" className="text-primary hover:underline">
                discoverflick@gmail.com
              </a>.
            </Section>

          </div>
        </main>
      </div>

      <BottomNav current="profile" />
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="font-editorial text-sm font-bold text-foreground mb-1.5">{title}</h3>
      <div>{children}</div>
    </div>
  );
}

function DataItem({ icon, label, desc }: { icon: string; label: string; desc: string }) {
  return (
    <div className="flex items-start gap-2.5 p-2.5 rounded-lg bg-surface border border-border">
      <span className="material-symbols-outlined text-[16px] text-primary shrink-0 mt-0.5">{icon}</span>
      <div>
        <p className="font-semibold text-foreground text-xs">{label}</p>
        <p className="text-[11px] text-foreground-secondary">{desc}</p>
      </div>
    </div>
  );
}
