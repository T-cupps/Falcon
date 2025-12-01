'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { MicrophoneIcon } from '@phosphor-icons/react/dist/ssr';

interface WelcomeViewProps {
  onStartCall: (playerName: string) => void;
}

export const WelcomeView = ({ onStartCall }: WelcomeViewProps) => {
  const [playerName, setPlayerName] = useState('');
  const [isConnecting, setIsConnecting] = useState(false);

  const handleStart = async () => {
    if (!playerName.trim()) {
      toast.error('Please enter your stage name');
      return;
    }

    setIsConnecting(true);
    toast.loading('Connecting to the stage...', { id: 'connecting' });

    try {
      await new Promise((resolve) => setTimeout(resolve, 500));
      onStartCall(playerName.trim());
      toast.success('Connected!', { id: 'connecting' });
    } catch (error) {
      toast.error('Connection failed, please try again.', { id: 'connecting' });
      setIsConnecting(false);
    }
  };

  return (
    <div className="relative min-h-screen w-full overflow-hidden font-sans">
      {/* Elegant Background */}
      <motion.div
        initial={{ scale: 1.05, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 1.5, ease: 'easeOut' }}
        className="absolute inset-0"
        style={{
          backgroundImage: `url('https://images.alphacoders.com/276/thumb-1920-276273.jpg')`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
      >
        <div className="absolute inset-0 bg-black/20" />
      </motion.div>

      {/* Main Content */}
      <div className="relative z-10 flex min-h-screen items-end justify-center p-6 pb-20">
        <motion.div
          initial={{ opacity: 0, y: 50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="w-full max-w-lg"
        >
          {/* Elegant Rectangular Card */}
          <div className="relative overflow-hidden rounded-3xl border border-white/20 bg-white/10 backdrop-blur-lg shadow-2xl ring-1 ring-purple-400/30">
            <div className="relative p-8 md:p-10">
              {/* Title & Icon */}
              <div className="mb-8 text-center">
                <motion.div
                  initial={{ scale: 0, rotate: -10 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ delay: 0.3, type: 'spring', stiffness: 200 }}
                  className="mb-4 flex justify-center"
                >
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 shadow-xl ring-2 ring-purple-300 animate-pulse">
                    <MicrophoneIcon size={32} weight="fill" className="text-white drop-shadow-md" />
                  </div>
                </motion.div>

                <h1 className="mb-2 text-3xl font-extrabold text-white md:text-4xl tracking-wide" style={{ textShadow: '0 0 10px rgba(186, 137, 206, 0.7)' }}>
                  Improv Battle
                </h1>
                <p className="text-sm text-purple-200/80 md:text-base">
                  Step onto the stage, unleash your creativity, and let the improv showdown begin!
                </p>
              </div>

              {/* Name Input */}
              <div className="mb-6">
                <label htmlFor="player-name" className="mb-2 block text-sm font-semibold text-white/90">
                  Stage Name
                </label>
                <input
                  id="player-name"
                  type="text"
                  value={playerName}
                  onChange={(e) => setPlayerName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !isConnecting) handleStart();
                  }}
                  placeholder="Heroic Name"
                  className="w-full rounded-xl border border-purple-300/50 bg-white/10 px-4 py-3 text-white placeholder:text-purple-200/50 backdrop-blur-sm focus:border-purple-400 focus:outline-none focus:ring-2 focus:ring-purple-400/40 transition-all shadow-md"
                  disabled={isConnecting}
                />
                <p className="mt-2 text-xs text-purple-200/60">
                  This is the way you will called on stage.
                </p>
              </div>

              {/* Start Button */}
              <motion.button
                whileHover={{ scale: 1.05, boxShadow: '0 0 25px rgba(168, 85, 247, 0.7)' }}
                whileTap={{ scale: 0.95 }}
                onClick={handleStart}
                disabled={isConnecting || !playerName.trim()}
                className="w-full rounded-xl bg-gradient-to-r from-indigo-500 to-purple-500 px-6 py-4 font-semibold text-white shadow-lg ring-1 ring-purple-300 transition-all disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isConnecting ? 'Connecting...' : 'Start Battle'}
              </motion.button>
            </div>
          </div>

          {/* Footer */}
          <p className="mt-8 text-center text-xs text-purple-200/40">
            Powered by Murf Falcon & LiveKit
          </p>
        </motion.div>
      </div>
    </div>
  );
};
