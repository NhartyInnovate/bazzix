import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { BazzixMark } from "./Logo";

const MESSAGES = [
  "Preparing your AI workspace...",
  "Initializing intelligent systems...",
  "Connecting securely...",
  "Loading your workspace...",
  "Almost ready...",
];

export function StartupScreen() {
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setMessageIndex((prev) => Math.min(prev + 1, MESSAGES.length - 1));
    }, 2500); // Change message every 2.5 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="relative flex min-h-dvh flex-col items-center justify-center bg-background overflow-hidden">
      {/* Ambient background glow */}
      <div
        className="pointer-events-none absolute left-1/2 top-1/2 z-0 h-[400px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-30 blur-[100px]"
        style={{
          background: "radial-gradient(circle at center, var(--color-primary) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10 flex flex-col items-center gap-8">
        {/* Animated Logo Container */}
        <motion.div
          initial={{ opacity: 0, scale: 0.9, filter: "blur(4px)" }}
          animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="relative flex items-center justify-center"
        >
          {/* Subtle pulsing aura behind the logo */}
          <motion.div
            animate={{
              scale: [1, 1.2, 1],
              opacity: [0.1, 0.3, 0.1],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "easeInOut",
            }}
            className="absolute inset-0 rounded-full bg-primary blur-xl"
          />
          <BazzixMark className="h-10 w-10 text-foreground relative z-10" />
        </motion.div>

        {/* Dynamic loading messages */}
        <div className="h-6 overflow-hidden flex items-center justify-center">
          <AnimatePresence mode="wait">
            <motion.p
              key={messageIndex}
              initial={{ opacity: 0, y: 10, filter: "blur(2px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={{ opacity: 0, y: -10, filter: "blur(2px)" }}
              transition={{ duration: 0.4, ease: "easeOut" }}
              className="text-sm font-medium text-muted-foreground tracking-wide"
            >
              {MESSAGES[messageIndex]}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
