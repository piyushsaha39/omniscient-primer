export interface IrisUtterance {
    text: string;
    channel?: 'left' | 'right' | 'center';
}

export function speakAsIris(text: string, onEnd?: () => void): void {
    if (!window.speechSynthesis) return;

    const voices = window.speechSynthesis.getVoices();
    // Priority: Samantha (Mac) > Zira (Windows) > Google US English > any English
    const irisVoice = voices.find(v => v.name.includes('Samantha'))
        || voices.find(v => v.name.includes('Zira'))
        || voices.find(v => v.name.includes('Google US English'))
        || voices.find(v => v.lang.startsWith('en'))
        || voices[0];

    const u = new SpeechSynthesisUtterance(text);
    u.voice = irisVoice || null;
    u.rate = 1.05;
    u.pitch = 1.08;
    u.volume = 1.0;

    if (onEnd) u.onend = onEnd;
    window.speechSynthesis.speak(u);
}

// Prepend Iris persona markers
export function irisGreeting(): string {
    const greetings = [
        "Greetings, boss.",
        "Yes, boss. I'm online.",
        "At your service, boss.",
        "Systems green, boss.",
        "Ready when you are, boss."
    ];
    return greetings[Math.floor(Math.random() * greetings.length)];
}

export function irisAcknowledge(): string {
    const acks = [
        "Copy that, boss.",
        "Understood, boss.",
        "On it, boss.",
        "Roger, boss."
    ];
    return acks[Math.floor(Math.random() * acks.length)];
}