'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useRoomContext, useRemoteParticipants } from '@livekit/components-react';
import {
  Microphone as MicrophoneIcon,
  MicrophoneSlash as MicrophoneSlashIcon,
  PhoneDisconnect as PhoneDisconnectIcon,
} from '@phosphor-icons/react';
import type { AppConfig } from '@/app-config';
import { useChatMessages } from '@/hooks/useChatMessages';
import { useConnectionTimeout } from '@/hooks/useConnectionTimout';
import { useDebugMode } from '@/hooks/useDebug';
import { cn } from '@/lib/utils';

const IN_DEVELOPMENT = process.env.NODE_ENV !== 'production';
const FIREFLY_COUNT = 20;

export const SessionView = ({ appConfig, onAnimationComplete }: { appConfig: AppConfig; onAnimationComplete?: () => void }) => {
  useConnectionTimeout(200_000);
  useDebugMode({ enabled: IN_DEVELOPMENT });

  const room = useRoomContext();
  const messages = useChatMessages();
  const participants = useRemoteParticipants();
  const transcriptRef = useRef<HTMLDivElement | null>(null);

  const [isMuted, setIsMuted] = useState(false);
  const [gamePhase, setGamePhase] = useState<'intro' | 'awaiting_improv' | 'reacting' | 'done'>('intro');
  const [currentRound, setCurrentRound] = useState(0);
  const [maxRounds] = useState(3);
  const [currentScenario, setCurrentScenario] = useState<string | null>(null);
  const [isHostSpeaking, setIsHostSpeaking] = useState(false);

  // small helpers to safely access potentially-unknown runtime participant fields
  const participantIsAgent = (p: any) => !!p?.isAgent;
  const participantIsLocal = (p: any) => !!p?.isLocal;
  const participantIdentity = (p: any) => (p?.identity ?? 'P');
  const participantAvatarLetter = (p: any) => (participantIdentity(p).charAt(0) || 'P').toUpperCase();

  // determine whether participant has audio active by inspecting runtime audio track objects
  const participantHasAudio = (p: any) => {
    try {
      const tracks = Array.from((p?.audioTracks?.values && typeof p.audioTracks.values === 'function') ? p.audioTracks.values() : []);
      // tracks entries may be keyed objects depending on LiveKit's runtime shape — cast to any and inspect
      return tracks.some((t: any) => {
        // try common shapes
        if (!t) return false;
        // often a wrapper: { track: { mediaStreamTrack: { readyState } }, subscribed, enabled, muted, kind }
        if (t.track?.mediaStreamTrack?.readyState === 'live') return true;
        if (t.track?.enabled === true) return true;
        if (t.subscribed === true) return true;
        // sometimes the track is the MediaStreamTrack itself
        if (typeof t.readyState === 'string' && t.readyState === 'live') return true;
        return false;
      });
    } catch (e) {
      return false;
    }
  };

  // Fireflies seed
  const generateFireflies = () =>
    Array.from({ length: FIREFLY_COUNT }, () => ({
      x: Math.random() * 100,
      y: Math.random() * 100,
      delay: Math.random() * 5,
      size: 2 + Math.random() * 4,
      glow: 0.15 + Math.random() * 0.6,
    }));
  const [fireflies] = useState(generateFireflies());

  // find agent participant safely (cast to any to read isAgent if it's a custom field)
  const agentParticipant = participants.find((p: any) => participantIsAgent(p));

  useEffect(() => {
    if (agentParticipant) {
      // audioTracks shape varies by SDK version; inspect safely
      const audioTracksArr = Array.from(((agentParticipant as any)?.audioTracks?.values ? (agentParticipant as any).audioTracks.values() : []) as any[]);
      const hasActiveAudio = audioTracksArr.some((t: any) => {
        if (!t) return false;
        if (t.track?.mediaStreamTrack?.readyState === 'live') return true;
        if (t.track?.enabled === true) return true;
        if (t.subscribed === true) return true;
        return false;
      });
      setIsHostSpeaking(Boolean(hasActiveAudio));
    } else {
      setIsHostSpeaking(false);
    }
  }, [agentParticipant, messages]);

  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    if (lastMessage && !((lastMessage.from as any)?.isLocal ?? false)) {
      const text = (lastMessage.message || '').toLowerCase();
      if (text.includes('round') && text.includes('of')) {
        const roundMatch = text.match(/round\s+(\d+)\s+of\s+(\d+)/i) || text.match(/round\s+(\d+)/i);
        if (roundMatch) {
          const roundNum = parseInt(roundMatch[1], 10);
          if (roundNum >= 1 && roundNum <= maxRounds) setCurrentRound(roundNum);
        }
      }
      if (text.includes('scenario') || text.includes('you are')) {
        setCurrentScenario(lastMessage.message);
        setGamePhase('awaiting_improv');
      }
      if (text.includes('that was') || text.includes('great') || text.includes('interesting') || text.includes('unique')) {
        setGamePhase('reacting');
      }
      if (text.includes('thank you for playing') || text.includes('end of our three rounds') || text.includes('closing summary')) {
        setGamePhase('done');
      }
    }
  }, [messages, maxRounds]);

  // single scroll helper (exposed as stable callback)
  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    const el = transcriptRef.current;
    if (!el) return;
    try {
      el.scrollTo({ top: el.scrollHeight, behavior });
    } catch {
      el.scrollTop = el.scrollHeight;
    }
  }, []);

  // Combined auto-scroll strategy:
  useEffect(() => {
    const el = transcriptRef.current;
    if (!el) return;

    // double rAF
    let raf1: number | undefined;
    let raf2: number | undefined;
    raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => scrollToBottom('auto'));
    });

    // fallback timeout
    const fallbackTimeout = window.setTimeout(() => scrollToBottom('auto'), 220);

    // ResizeObserver
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      let lastHeight = el.scrollHeight;
      ro = new ResizeObserver(() => {
        if (el.scrollHeight !== lastHeight) {
          lastHeight = el.scrollHeight;
          scrollToBottom('smooth');
        }
      });
      ro.observe(el);
    }

    return () => {
      if (raf1) cancelAnimationFrame(raf1);
      if (raf2) cancelAnimationFrame(raf2);
      clearTimeout(fallbackTimeout);
      if (ro) ro.disconnect();
    };
  }, [messages, scrollToBottom]);

  const toggleMute = async () => {
    const enabled = !isMuted;
    try {
      // guard room.localParticipant presence
      if (room?.localParticipant?.setMicrophoneEnabled) {
        await (room.localParticipant as any).setMicrophoneEnabled(enabled);
      }
      setIsMuted(!enabled);
    } catch (e) {
      console.error('toggleMute error', e);
    }
  };

  const handleLeave = () => {
    room.disconnect();
    if (onAnimationComplete) onAnimationComplete();
  };

  const getPhaseLabel = () => {
    switch (gamePhase) {
      case 'intro':
        return 'Intro';
      case 'awaiting_improv':
        return 'Playing scene';
      case 'reacting':
        return 'Host reacting';
      case 'done':
        return 'Summary';
      default:
        return 'In game';
    }
  };

  return (
    <div className="relative h-screen w-full overflow-hidden text-white">
      {/* Background (kept the same magical forest) */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1.6 }}
        className="absolute inset-0"
        style={{
          backgroundImage: `url('https://images.alphacoders.com/276/276273.jpg')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-br from-black/75 via-purple-900/55 to-indigo-900/45" />

        <motion.div
          animate={{ opacity: [0.02, 0.06, 0.02] }}
          transition={{ duration: 12, repeat: Infinity }}
          className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(255,255,255,0.02),transparent 30%)]"
        />

        {fireflies.map((fly, idx) => (
          <motion.div
            key={idx}
            initial={{ x: `${fly.x}%`, y: `${fly.y}%`, opacity: 0 }}
            animate={{
              x: [`${fly.x}%`, `${fly.x + Math.random() * 8 - 4}%`],
              y: [`${fly.y}%`, `${fly.y + Math.random() * 8 - 4}%`],
              opacity: [0, fly.glow, 0],
            }}
            transition={{ repeat: Infinity, repeatType: 'mirror', duration: 5 + Math.random() * 5, delay: fly.delay }}
            className="absolute rounded-full bg-yellow-200/80 blur-sm"
            style={{ width: fly.size, height: fly.size }}
          />
        ))}
      </motion.div>

      <div className="relative z-10 grid h-full grid-cols-1 lg:grid-cols-3">
        <div className="col-span-2 flex flex-col">
          <div className="border-b border-white/6 bg-gradient-to-b from-white/3 to-transparent py-4 px-6 backdrop-blur-sm">
            <div className="mx-auto max-w-7xl flex items-center justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <span className="inline-flex items-center rounded-full bg-purple-600/20 px-3 py-1 text-xs font-semibold text-purple-200 animate-pulse drop-shadow-[0_0_8px_rgba(186,137,206,0.7)]">
                    LIVE
                  </span>
                  <div className="text-sm font-medium text-white/80">{getPhaseLabel()}</div>
                </div>
                <h2 className="mt-2 text-2xl font-bold tracking-tight text-white drop-shadow-lg">
                  {currentRound > 0 ? `Round ${currentRound} of ${maxRounds}` : 'Improv Battle — Enchanted Grove'}
                </h2>
                {currentScenario && <p className="mt-1 max-w-2xl text-sm text-purple-200/80 line-clamp-2">{currentScenario}</p>}
              </div>

              <div className="flex items-center gap-3">
                {isHostSpeaking && (
                  <motion.div animate={{ scale: [1, 1.08, 1] }} transition={{ duration: 1.4, repeat: Infinity }} className="flex items-center gap-2 rounded-full bg-purple-600/20 px-4 py-2">
                    <div className="h-2 w-2 rounded-full bg-purple-300 animate-pulse" />
                    <span className="text-xs font-medium text-purple-200">Host speaking</span>
                  </motion.div>
                )}

                <div className="flex gap-2 items-center">
                  <div className="text-xs text-white/70">Theme</div>
                  <div className="rounded-md bg-white/6 px-3 py-1 text-sm">Dark Forest • Genshin Vibe</div>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-1 overflow-hidden px-6 py-6">
            <div ref={transcriptRef} className="mx-auto w-full max-w-4xl space-y-4 overflow-y-auto pr-4">
              {messages.length === 0 ? (
                <div className="flex h-full min-h-[200px] items-center justify-center">
                  <p className="text-white/40">The forest waits — say something to begin the show...</p>
                </div>
              ) : (
                messages.map((message: any, idx: number) => {
                  const isLocal = ((message.from as any)?.isLocal) ?? false;
                  const isHost = !isLocal && ((message.from as any)?.isAgent ?? false);
                  const isLast = idx === messages.length - 1;
                  return (
                    <motion.div
                      key={message.id ?? idx}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      onAnimationComplete={isLast ? () => scrollToBottom('smooth') : undefined}
                      className={cn('flex', isLocal ? 'justify-end' : 'justify-start')}
                    >
                      <div
                        className={cn(
                          'max-w-[78%] px-5 py-3 rounded-2xl border backdrop-blur-md transition-all',
                          isHost
                            ? 'bg-gradient-to-tr from-purple-600/30 to-indigo-600/20 text-white border-purple-400/20'
                            : isLocal
                            ? 'bg-gradient-to-tr from-indigo-600/25 to-purple-500/20 text-white border-indigo-300/10'
                            : 'bg-white/6 text-white/90 border-white/6'
                        )}
                      >
                        <div className="mb-1 text-xs font-semibold opacity-80">{isHost ? 'Host' : isLocal ? 'You' : 'Player'}</div>
                        <div className="text-sm leading-relaxed whitespace-pre-wrap">{message.message}</div>
                      </div>
                    </motion.div>
                  );
                })
              )}
            </div>

            <div className="hidden w-64 flex-col items-center gap-4 pl-6 lg:flex">
              <div className="rounded-lg bg-white/4 p-3 text-center backdrop-blur-md">
                <div className="text-xs text-white/80">Current Phase</div>
                <div className="mt-2 text-sm font-semibold">{getPhaseLabel()}</div>
              </div>

              <div className="rounded-lg bg-white/3 p-3 backdrop-blur-md text-sm">
                <div className="text-xs text-white/80">Rounds</div>
                <div className="mt-1 font-medium">{currentRound} / {maxRounds}</div>
              </div>
            </div>
          </div>

          <div className="border-t border-white/6 bg-gradient-to-t from-transparent to-black/10 py-4 px-6 backdrop-blur-sm">
            <div className="mx-auto max-w-7xl flex items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="rounded-full bg-white/8 px-4 py-2 text-sm">{getPhaseLabel()}</div>

                <div className="hidden items-center gap-2 rounded-full bg-white/6 px-3 py-2 md:flex">
                  <div className="text-xs">Auto-save transcript</div>
                  <div className="ml-2 inline-block h-4 w-8 rounded-full bg-white/10" />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.96 }}
                  onClick={toggleMute}
                  className={cn(
                    'flex h-12 w-12 items-center justify-center rounded-full transition-all shadow-sm',
                    isMuted
                      ? 'bg-red-600/20 text-red-300 hover:bg-red-600/30'
                      : 'bg-gradient-to-br from-indigo-600/30 to-purple-600/25 text-white hover:brightness-105'
                  )}
                >
                  {isMuted ? <MicrophoneSlashIcon size={20} weight="fill" /> : <MicrophoneIcon size={20} weight="fill" />}
                </motion.button>

                <motion.button
                  whileHover={{ scale: 1.03 }}
                  whileTap={{ scale: 0.96 }}
                  onClick={handleLeave}
                  className="flex h-12 items-center gap-2 rounded-full bg-red-600/20 px-5 text-red-300 transition-all hover:bg-red-600/30"
                >
                  <PhoneDisconnectIcon size={18} weight="fill" />
                  <span className="text-sm font-medium">Leave</span>
                </motion.button>
              </div>
            </div>
          </div>
        </div>

        <aside className="hidden flex-col gap-4 border-l border-white/6 bg-white/3 p-6 backdrop-blur-md lg:flex">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-white/80">Participants</div>
              <div className="font-semibold">{participants.length} in room</div>
            </div>
            <div className="text-xs text-white/60">Host</div>
          </div>

          <div className="flex flex-col gap-3 overflow-y-auto">
            {participants.map((p: any) => (
              <div key={participantIdentity(p)} className="flex items-center gap-3 rounded-lg bg-white/6 p-3">
                <div className="h-10 w-10 shrink-0 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-sm font-bold">{participantAvatarLetter(p)}</div>
                <div className="flex-1">
                  <div className="text-sm font-medium">{participantIdentity(p)}</div>
                  <div className="text-xs text-white/60">{participantIsAgent(p) ? 'Agent (Host)' : participantIsLocal(p) ? 'You' : 'Player'}</div>
                </div>
                <div className="text-xs text-white/60">{participantHasAudio(p) ? '🔊' : '🔈'}</div>
              </div>
            ))}
          </div>

          <div className="mt-auto flex flex-col gap-3">
            <button onClick={() => {}} className="rounded-md bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-2 text-sm font-medium">Audience applause</button>
            <button onClick={() => {}} className="rounded-md bg-white/6 px-4 py-2 text-sm">Toggle captions</button>
          </div>
        </aside>
      </div>
    </div>
  );
};
