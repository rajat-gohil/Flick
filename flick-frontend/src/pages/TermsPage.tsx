import React from "react";
import { useNavigate } from "react-router-dom";
import CinemaHeader from "../components/CinemaHeader";
import BottomNav from "../components/BottomNav";

export default function TermsPage() {
  const navigate = useNavigate();

  return (
    <div className="bg-background font-sans text-foreground min-h-screen flex flex-col antialiased">

      {/* Header */}
      <CinemaHeader
        current="profile"
        title="Terms of Service"
        subtitle="Rules of Engagement"
        onBack={() => {
          if (window.history.length > 1) navigate(-1);
          else navigate("/profile");
        }}
      />

      <div className="w-full max-w-2xl mx-auto flex-1 flex flex-col px-4 sm:px-6 py-6 pb-24 md:pb-12">
        <main className="flex-1 overflow-y-auto">

          <div className="flex items-center gap-3.5 mb-6 pb-4 border-b border-border/60">
            <div className="size-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <span className="material-symbols-outlined text-[22px]">gavel</span>
            </div>
            <div>
              <h2 className="font-editorial text-xl font-bold">Flick Terms of Engagement</h2>
              <p className="text-[11px] text-foreground-secondary">Last updated: March 2026</p>
            </div>
          </div>

          <div className="flex flex-col gap-6 text-xs text-foreground-secondary leading-relaxed">

            <Section title="1. Acceptance of Terms">
              By creating a member account or accessing Flick, you agree to be bound by these Terms of Service. If you do not accept these terms in their entirety, please refrain from using the platform.
            </Section>

            <Section title="2. Eligibility">
              You must be at least 13 years of age to access Flick. By utilizing Flick, you confirm that you meet this requirement. Minors must have authorized parental consent.
            </Section>

            <Section title="3. Member Credentials">
              You remain responsible for maintaining the confidentiality of your authentication credentials and for all collaborative activities carried out through your member account. Notify us promptly at support@flickapp.in if you suspect unauthorized access.
            </Section>

            <Section title="4. Standards of Conduct">
              You agree not to:
              <ul className="list-disc pl-5 mt-2 flex flex-col gap-1 text-foreground-secondary">
                <li>Use the service for unlawful purposes</li>
                <li>Attempt unauthorized probing or interception of API endpoints</li>
                <li>Deploy automated harvesting bots against catalog records</li>
                <li>Impersonate any other member or entity</li>
              </ul>
            </Section>

            <Section title="5. Movie Metadata & Posters">
              Film data, synopses, and poster graphics are provided through{" "}
              <a href="https://www.themoviedb.org" target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
                The Movie Database (TMDB)
              </a>. Flick operates independently and is not formally endorsed by or affiliated with TMDB or individual film studios.
            </Section>

            <Section title="6. Streaming Availability">
              Streaming channel information is aggregated via third-party catalog registries. While updated regularly, Flick cannot guarantee perpetual accuracy or regional availability without variation.
            </Section>

            <Section title="7. Privacy Policy">
              Your use of Flick is governed additionally by our{" "}
              <button onClick={() => navigate("/privacy")} className="text-primary hover:underline font-semibold">
                Privacy Policy
              </button>
              , incorporated into these terms by reference.
            </Section>

            <Section title="8. Intellectual Property">
              The Flick identity, typographical assets, and design system are the proprietary creation of Flick. Unauthorized copying or redistribution is strictly prohibited.
            </Section>

            <Section title="9. Contact">
              For legal inquiries, contact{" "}
              <a href="mailto:legal@flickapp.in" className="text-primary hover:underline">
                legal@flickapp.in
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
