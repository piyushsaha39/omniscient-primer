let audioCtx: AudioContext | null = null;

export function getAudioContext(): AudioContext {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
    }
    return audioCtx;
}

// Synthesize directional tones for UI feedback
export function playVoidTone(channel: 'left' | 'right' | 'center', type: 'enter' | 'exit' | 'pulse') {
    const ctx = getAudioContext();
    const osc = ctx.createOscillator();
    const panner = ctx.createStereoPanner();
    const gain = ctx.createGain();

    const freqs = { enter: 220, exit: 110, pulse: 440 };
    const panVal = channel === 'left' ? -0.8 : channel === 'right' ? 0.8 : 0;

    osc.type = type === 'pulse' ? 'sine' : 'triangle';
    osc.frequency.setValueAtTime(freqs[type], ctx.currentTime);

    if (type === 'enter') {
        osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.3);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    } else if (type === 'exit') {
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);
    } else {
        gain.gain.setValueAtTime(0.05, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
    }

    panner.pan.value = panVal;

    osc.connect(panner);
    panner.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + (type === 'exit' ? 0.8 : 0.5));
}