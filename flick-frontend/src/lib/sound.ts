/**
 * Flick Cinematic Micro-Audio Synthesizer (Web Audio API)
 * Built for tactile, organic acoustic feedback during film screening deck interactions.
 * 
 * Features:
 * - 0 external audio assets, 0 network requests, 0 bundle weight.
 * - Gentle acoustic frequencies tuned for an art-house cinema aesthetic.
 * - Resilient: non-blocking, safe in SSR/test environments, respects silent policies.
 */

class SoundSynthesizer {
  private ctx: AudioContext | null = null;
  private enabled = true;

  private getContext(): AudioContext | null {
    if (!this.enabled || typeof window === "undefined") return null;
    try {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioCtx) return null;
      if (!this.ctx) {
        this.ctx = new AudioCtx();
      }
      if (this.ctx.state === "suspended") {
        this.ctx.resume().catch(() => {});
      }
      return this.ctx;
    } catch {
      return null;
    }
  }

  /**
   * Soft, warm acoustic click on "Consider" / Like
   * Ascending sine 420Hz -> 580Hz over 45ms with smooth exponential decay
   */
  playLike() {
    const ctx = this.getContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(420, now);
      osc.frequency.exponentialRampToValueAtTime(580, now + 0.045);

      gain.gain.setValueAtTime(0.04, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.045);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.045);
    } catch {
      // Safe no-op on audio restrictions
    }
  }

  /**
   * Soft, muted acoustic thud on "Pass" / Dislike
   * Descending triangle wave 260Hz -> 160Hz over 40ms with fast decay
   */
  playPass() {
    const ctx = this.getContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "triangle";
      osc.frequency.setValueAtTime(260, now);
      osc.frequency.exponentialRampToValueAtTime(160, now + 0.04);

      gain.gain.setValueAtTime(0.035, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.04);
    } catch {
      // Safe no-op on audio restrictions
    }
  }

  /**
   * Resonant golden two-tone chime for "Superlike" / Priority Interest
   * D5 (587Hz) to A5 (880Hz) to D6 (1174Hz) harmonic progression
   */
  playSuperlike() {
    const ctx = this.getContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      const osc1 = ctx.createOscillator();
      const osc2 = ctx.createOscillator();
      const gain = ctx.createGain();

      osc1.type = "sine";
      osc1.frequency.setValueAtTime(587.33, now);
      osc1.frequency.exponentialRampToValueAtTime(880, now + 0.09);

      osc2.type = "sine";
      osc2.frequency.setValueAtTime(880, now + 0.04);
      osc2.frequency.exponentialRampToValueAtTime(1174.66, now + 0.16);

      gain.gain.setValueAtTime(0.05, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);

      osc1.connect(gain);
      osc2.connect(gain);
      gain.connect(ctx.destination);

      osc1.start(now);
      osc1.stop(now + 0.09);
      osc2.start(now + 0.04);
      osc2.stop(now + 0.18);
    } catch {
      // Safe no-op on audio restrictions
    }
  }

  /**
   * Gentle reverse tone on "Undo" / Recall
   * Descending-to-ascending sine 340Hz -> 480Hz over 50ms
   */
  playUndo() {
    const ctx = this.getContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(340, now);
      osc.frequency.exponentialRampToValueAtTime(480, now + 0.05);

      gain.gain.setValueAtTime(0.035, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.05);
    } catch {
      // Safe no-op on audio restrictions
    }
  }

  /**
   * Subtle high-frequency tactile tick when crossing 100px commit threshold
   */
  playCommitTick() {
    const ctx = this.getContext();
    if (!ctx) return;
    try {
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(800, now);
      osc.frequency.exponentialRampToValueAtTime(1200, now + 0.015);

      gain.gain.setValueAtTime(0.02, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.015);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start(now);
      osc.stop(now + 0.015);
    } catch {
      // Safe no-op on audio restrictions
    }
  }
}

export const sound = new SoundSynthesizer();
