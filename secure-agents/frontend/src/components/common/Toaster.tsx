import { ToastNotification, ToastNotificationProps } from "@carbon/react";
// import * as motion from "motion/react-client";
import { AnimatePresence, motion } from "motion/react";
import { useState, useEffect } from "react";

type ToastType = Exclude<ToastNotificationProps["kind"], undefined>;

const TOAST_EVENT = "toast-notification";
const DEFAULT_DURATION = 3000;

interface Toast {
  id: string;
  message: string;
  type: ToastType;
  title: string;
  caption?: string;
}

type ToastEvent = CustomEvent<{
  message: string;
  type: ToastType;
  title: string;
  caption?: string;
  duration?: number;
}>;

interface ToastOptions {
  title?: string;
  caption?: string;
  duration?: number;
}

// functions to create a toast
export const toast = {
  success: (message: string, options?: ToastOptions) => {
    window.dispatchEvent(
      new CustomEvent(TOAST_EVENT, {
        detail: {
          message,
          type: "success",
          title: options?.title || "Success",
          caption: options?.caption,
          duration: options?.duration,
        },
      }),
    );
  },
  error: (message: string, options?: ToastOptions) => {
    window.dispatchEvent(
      new CustomEvent(TOAST_EVENT, {
        detail: {
          message,
          type: "error",
          title: options?.title || "Error",
          caption: options?.caption,
          duration: options?.duration,
        },
      }),
    );
  },
  warning: (message: string, options?: ToastOptions) => {
    window.dispatchEvent(
      new CustomEvent(TOAST_EVENT, {
        detail: {
          message,
          type: "warning",
          title: options?.title || "Warning",
          caption: options?.caption,
          duration: options?.duration,
        },
      }),
    );
  },
  info: (message: string, options?: ToastOptions) => {
    window.dispatchEvent(
      new CustomEvent(TOAST_EVENT, {
        detail: {
          message,
          type: "info",
          title: options?.title || "Info",
          caption: options?.caption,
          duration: options?.duration,
        },
      }),
    );
  },
  infoSquare: (message: string, options?: ToastOptions) => {
    window.dispatchEvent(
      new CustomEvent(TOAST_EVENT, {
        detail: {
          message,
          type: "info-square",
          title: options?.title || "Info",
          caption: options?.caption,
          duration: options?.duration,
        },
      }),
    );
  },
  warningAlt: (message: string, options?: ToastOptions) => {
    window.dispatchEvent(
      new CustomEvent(TOAST_EVENT, {
        detail: {
          message,
          type: "warning-alt",
          title: options?.title || "Warning",
          caption: options?.caption,
          duration: options?.duration,
        },
      }),
    );
  },
};

export function Toaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    const handleToast = (event: ToastEvent) => {
      const {
        message,
        type,
        title,
        caption: customCaption,
        duration,
      } = event.detail;

      const caption =
        customCaption ||
        new Date().toLocaleTimeString("en-US", {
          hour12: true,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        });

      const newToast = {
        id: Math.random().toString(36).substring(2, 9),
        message,
        type,
        title,
        caption,
      };

      setToasts((prev) => [...prev, newToast]);

      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== newToast.id));
      }, duration || DEFAULT_DURATION);
    };

    window.addEventListener(TOAST_EVENT, handleToast as EventListener);
    return () =>
      window.removeEventListener(TOAST_EVENT, handleToast as EventListener);
  }, []);

  return (
    <div className="fixed right-4 top-16 z-[9999] flex flex-col">
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            layout
            initial={{ x: 100, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 100, opacity: 0 }}
            transition={{
              duration: 0.2,
              layout: { duration: 0.2 },
            }}
          >
            <ToastNotification
              className="mb-2"
              kind={toast.type}
              title={toast.title}
              subtitle={toast.message}
              caption={toast.caption}
              onClose={() => {
                setToasts((prev) => prev.filter((t) => t.id !== toast.id));
                return false;
              }}
            />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
