'use client';
import { AnimatePresence, motion } from 'framer-motion';
import { type ReceivedChatMessage } from '@livekit/components-react';
import { ShimmerText } from '@/components/livekit/shimmer-text';
import { cn } from '@/lib/utils';

const MotionMessage = motion.p;

const VIEW_MOTION_PROPS = {
  variants: {
    visible: { opacity: 1 },
    hidden: { opacity: 0 },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    ease: 'linear',
    duration: 0.5,
    delay: 0.8,
  },
};

interface SessionViewProps {
  messages?: ReceivedChatMessage[];
  className?: string;
  appConfig?: { [key: string]: any };
}

export function SessionView({ className, messages = [], appConfig }: SessionViewProps) {
  return (
    <AnimatePresence>
      {messages.length === 0 && (
        <MotionMessage
          variants={VIEW_MOTION_PROPS.variants}
          initial={VIEW_MOTION_PROPS.initial}
          animate={VIEW_MOTION_PROPS.animate}
          exit={VIEW_MOTION_PROPS.exit}
          transition={VIEW_MOTION_PROPS.transition}
          aria-hidden={messages.length > 0}
          className={cn('pointer-events-none text-center', className)}
        >
          <ShimmerText className="text-sm font-semibold">
            {appConfig?.customMessage || 'Session View Content'}
          </ShimmerText>
        </MotionMessage>
      )}
    </AnimatePresence>
  );
}
